"""Native core N2.3, the Python half: Spectrum's fixed-layout native schema and the slot-head ``payload_schema`` check.

Transport rule 3 to 5 (``Docs/Future_Work/Native_Core_P3_Decisions.md``): a mode's native record has explicit offsets,
little-endian, 16-byte aligned, a version, and carries exactly what its renderer reads (Spectrum's field list is the
renderer's own input declaration, ``spectrum_frame_inputs``); ``payload_schema`` 1 is the tagged codec and a native id
is ``(version << 16) | 0x100 | mode_code``; a reader admits a slot by its head before any payload copy and refuses an
unknown schema or mode code, a newer version or a size disagreeing with the layout: counted, never acknowledged, the
stream failed and reported on the owner's session-end edge. Every refusal has its negative control: a reader without
the head check (``FramePacketReader`` with no ``admit``, the pre-N2.3 reader) accepts the same slot.
"""
from __future__ import annotations

import dataclasses
import inspect
import struct
from multiprocessing import Pipe
from multiprocessing.shared_memory import SharedMemory

import pytest

from core.visualizer_engine import frame_codec, native_schema
from core.visualizer_engine import spectrum_native_schema as spectrum
from core.visualizer_engine.packet_abi import MODE_CODES, FramePacketReader, FramePacketWriter
from core.visualizer_engine.packet_mailbox import PacketMailbox
from widgets.spotify_visualizer.spectrum_frame_inputs import (
    MAX_LEVELS,
    SPECTRUM_FRAME_FIELDS_NOT_DRAWN,
    SPECTRUM_FRAME_INPUTS,
)

#: Version 1's layout. A change to the frame-input declaration or the layout rule changes it: raise
#: ``spectrum_native_schema.VERSION`` and record the new fingerprint here (the C++ reader follows the version).
SPECTRUM_V1_FINGERPRINT = "b98ca5a1be307b36"


# ------------------------------------------------------------------------------------------- real Spectrum frames

@pytest.fixture(scope="module")
def spectrum_frames():
    """The logical frames the production owner hands its renderer while it replays the shipped clip on Spectrum."""
    from PySide6.QtWidgets import QApplication

    import tools.expanded_visualizer_evidence as evidence
    from widgets.spotify_visualizer.render_bridge import VisualizerSnapshotBridge

    QApplication.instance() or QApplication([])
    frames = []
    publish = VisualizerSnapshotBridge.publish

    def recording(self, snapshot):
        frames.append(snapshot.logical)
        return publish(self, snapshot)

    VisualizerSnapshotBridge.publish = recording
    try:
        evidence.owner_replay(evidence.shipped_clip(1.5), "spectrum")
    finally:
        VisualizerSnapshotBridge.publish = publish
    frames = [frame for frame in frames if frame.mode_id == "spectrum"]
    assert len(frames) > 30
    return frames


def _tagged(frame):
    """What the Python consumer receives today: the frame through the tagged codec."""
    return frame_codec.decode(frame_codec.encode((1, 1, 0.0, frame)))[3]


def _variants(frame):
    """``frame`` with every declared input moved off its value (derived from the declaration, never from authored
    content): every choice of each table and one outside it, booleans flipped, three-channel colours, -0.0 and odd
    reals, more levels than the renderer keeps, and a style without the optional gap."""
    parameters = dict(frame.mode_state.parameters.entries)
    style = dict(frame.common.style.entries)
    out = []
    for entry in SPECTRUM_FRAME_INPUTS:
        if entry.source not in ("parameters", "style"):
            continue
        target = parameters if entry.source == "parameters" else style
        current = target.get(entry.name)
        if entry.kind == "enum":
            values = [*entry.table, "not a choice"]
        elif entry.kind == "bool":
            values = [not current]
        elif entry.kind == "rgba":
            values = [(17, 34, 51), (1.5, 254.25, 0.0, 128)]
        elif entry.kind == "f64":
            values = [-0.0, 0.1 + 0.2, 1e-300]
        else:
            values = []
        for value in values:
            moved = dict(target, **{entry.name: value})
            if entry.source == "parameters":
                state = dataclasses.replace(frame.mode_state, parameters=moved)
                out.append(dataclasses.replace(frame, mode_state=state))
            else:
                out.append(dataclasses.replace(frame, common=dataclasses.replace(frame.common, style=moved)))
    style.pop("bar_gap", None)
    out.append(dataclasses.replace(frame, common=dataclasses.replace(frame.common, style=style)))
    long = tuple(0.001 * index for index in range(MAX_LEVELS + 6))
    out.append(dataclasses.replace(
        frame, playing=not frame.playing,
        common=dataclasses.replace(frame.common, bars=long, bar_count=len(long)),
        mode_state=dataclasses.replace(frame.mode_state, peaks=long[:5])))
    return out


@pytest.mark.qt
def test_real_spectrum_frames_round_trip_bit_for_bit_against_the_tagged_codec(spectrum_frames):
    frames = list(spectrum_frames)
    frames += _variants(frames[len(frames) // 2])
    for frame in frames:
        tagged = _tagged(frame)
        record = spectrum.encode(frame)
        assert len(record) == spectrum.LAYOUT.size and record == spectrum.encode(tagged)
        # repr keeps every float's 64 bits (and the sign of zero): bit for bit.
        assert repr(spectrum.decode(record)) == repr(spectrum.project(tagged))


@pytest.mark.qt
def test_the_round_trip_comparison_sees_a_single_float_bit(spectrum_frames):
    # Negative control for the round trip: a reader that rounded the bars through float32 (the shader's precision)
    # differs from the tagged decode on the real frames, so the comparison above is bit-exact, not approximate.
    def float32(values):
        return tuple(struct.unpack("<f", struct.pack("<f", value))[0] for value in values)

    differs = 0
    for frame in spectrum_frames:
        decoded = spectrum.decode(spectrum.encode(frame))
        decoded["bars"] = float32(decoded["bars"])
        differs += repr(decoded) != repr(spectrum.project(_tagged(frame)))
    assert differs > 0


def test_the_record_carries_what_the_renderer_reads_from_one_declaration():
    # The SpectrumFrame's fields are each carried, deliberately not drawn, or the parameters the declaration expands.
    from widgets.spotify_visualizer.render_state import SpectrumFrame

    carried = {entry.name for entry in SPECTRUM_FRAME_INPUTS if entry.source == "mode_state"}
    assert {field.name for field in dataclasses.fields(SpectrumFrame)} == (
        carried | set(SPECTRUM_FRAME_FIELDS_NOT_DRAWN) | {"parameters"})
    # Every declared input is a field of the record (a level sequence with its kept length).
    names = {field.name for field in spectrum.LAYOUT.fields}
    for entry in SPECTRUM_FRAME_INPUTS:
        assert entry.name in names
        if entry.kind == "levels":
            assert spectrum.LAYOUT.field(entry.name).count == MAX_LEVELS and f"{entry.name}_len" in names
    # The renderer reads its frame's style and parameters only through the declaration (its per-frame fetch and the
    # decoration's), never by a name of its own.
    from rendering.quick.visualizer.implementations import spectrum as renderer
    source = inspect.getsource(renderer.QuickSpectrumRenderer.render)
    assert _renderer_reads_only_declared(source)
    declared = {entry.name for entry in SPECTRUM_FRAME_INPUTS if entry.source == "parameters"}
    assert set(renderer._PER_FRAME_PARAMETERS) | set(renderer._DECOR_SOURCES) == declared


def _renderer_reads_only_declared(source: str) -> bool:
    return not any(text in source for text in ("parameter(parameters", "parameters[", ".style[", ".style.get("))


def test_the_declaration_check_sees_a_renderer_that_reads_its_own_names():
    # Negative control: the renderer's render() before N2.3 read its parameters by name (``parameter(parameters,
    # "rainbow_speed")``) and its style directly; the check above refuses that shape.
    before = 'rainbow_speed = float(parameter(parameters, "rainbow_speed"))\nbar_gap=logical.common.style.get("bar_gap")'
    assert not _renderer_reads_only_declared(before)


def _layout_problems(layout) -> list[str]:
    problems = []
    if [f.name for f in layout.fields[:2]] != ["payload_schema", "record_bytes"] or layout.fields[0].offset != 0 \
            or layout.fields[1].offset != 4:
        problems.append("header words")
    end = 0
    for field in sorted(layout.fields, key=lambda f: f.offset):
        if field.offset < end:
            problems.append(f"{field.name} overlaps")
        if (field.is_array or field.kind == "f64x4") and field.offset % native_schema.NATIVE_ALIGNMENT:
            problems.append(f"{field.name} not 16-byte aligned")
        if field.kind == "f64" and field.offset % 8:
            problems.append(f"{field.name} not 8-byte aligned")
        end = field.offset + field.size
    if end > layout.size or layout.size % native_schema.NATIVE_ALIGNMENT:
        problems.append("record size")
    return problems


def test_the_layout_is_explicit_aligned_and_pinned_to_its_version():
    assert _layout_problems(spectrum.LAYOUT) == []
    assert spectrum.LAYOUT.fingerprint() == SPECTRUM_V1_FINGERPRINT, (
        "Spectrum's native record changed: raise VERSION and record the new fingerprint\n" + spectrum.LAYOUT.table())
    assert spectrum.SCHEMA_ID == native_schema.native_schema_id(MODE_CODES["spectrum"], spectrum.VERSION)
    # Negative controls: a misaligned array, and one more field, are both seen.
    shifted = native_schema.NativeLayout(
        tuple(dataclasses.replace(f, offset=f.offset + 8) if f.name == "bars" else f for f in spectrum.LAYOUT.fields),
        spectrum.LAYOUT.size)
    assert _layout_problems(shifted)
    grown = native_schema.NativeLayout.build(spectrum._layout_entries() + (("one_more", "u32", 1),))
    assert grown.fingerprint() != SPECTRUM_V1_FINGERPRINT


# --------------------------------------------------------------------------------------------- the namespaces

@pytest.mark.qt
def test_no_native_schema_id_collides_with_the_tagged_codec_and_the_codec_refuses_a_native_payload(spectrum_frames):
    schemas = native_schema.native_schemas()
    assert schemas and frame_codec.CODEC_SCHEMA not in schemas
    for schema_id, schema in schemas.items():
        assert native_schema.parse_native_schema_id(schema_id) == (schema.mode_code, schema.version)
        assert schema_id & 0xFFFF >= 0x101         # the codec's u16 prefix can never read as 1
    for reserved in (0, frame_codec.CODEC_SCHEMA, *range(2, 0x100)):
        assert native_schema.parse_native_schema_id(reserved) is None
    record = spectrum.encode(spectrum_frames[0])
    with pytest.raises(frame_codec.FrameCodecError):
        frame_codec.decode(record)
    # Negative control: a decoder that skipped the codec's prefix check would read the record's bytes as tags.
    assert struct.unpack_from("<H", record, 0)[0] != frame_codec.CODEC_SCHEMA


# ---------------------------------------------------------------------------------------- the slot-head check

def _bad_slot(cause):
    """(payload_schema, slot mode code, payload) for one refusal on a native stream."""
    good = spectrum.SCHEMA_ID
    size = spectrum.LAYOUT.size
    return {
        "reserved schema": (2, 1, bytes(size)),
        "malformed schema": (good | 0x01000000, 1, bytes(size)),
        "unknown mode code": (good, 200, bytes(size)),
        "mode disagrees": (good, MODE_CODES["oscilloscope"], bytes(size)),
        "mode without a schema": (native_schema.native_schema_id(MODE_CODES["oscilloscope"], 1),
                                  MODE_CODES["oscilloscope"], bytes(size)),
        "newer version": (native_schema.native_schema_id(1, spectrum.VERSION + 1), 1, bytes(size)),
        "short record": (good, 1, bytes(size - 16)),
        "codec payload": (frame_codec.CODEC_SCHEMA, 1, frame_codec.encode((1, 1, 0.0, None))),
    }[cause]


_NATIVE_CASES = {
    "reserved schema": "schema", "malformed schema": "schema", "unknown mode code": "mode", "mode disagrees": "mode",
    "mode without a schema": "schema", "newer version": "version", "short record": "size", "codec payload": "schema",
}


def _publish_raw(mapping, schema, mode, payload):
    memory = SharedMemory(name=mapping)
    writer = FramePacketWriter(memory.buf)
    try:
        return writer.publish(payload, payload_schema=schema, logical_timestamp=1.0, mode_code=mode,
                              runtime_generation=3, activation_id=4)
    finally:
        writer.release()
        memory.close()


def _consumed(mapping):
    memory = SharedMemory(name=mapping)
    writer = FramePacketWriter(memory.buf)
    try:
        return writer.consumed_sequence
    finally:
        writer.release()
        memory.close()


def _accepted_without_the_check(mapping):
    """Negative control: the pre-N2.3 reader (no head check) on the same mapping hands the bad slot out."""
    memory = SharedMemory(name=mapping)
    reader = FramePacketReader(memory.buf)
    try:
        return reader.read_latest() is not None
    finally:
        reader.release()
        memory.close()


def _assert_refused(payload_kind, schema, mode, payload, cause):
    receiver, sender = Pipe(duplex=False)
    failed = []
    mailbox = PacketMailbox(role="reader", slot_bytes=64 * 1024, payload=payload_kind)
    try:
        mailbox.listen_for_wakes(receiver, on_closed=lambda: failed.append(mailbox.payload_failure))
        sequence = _publish_raw(mailbox.mapping_name, schema, mode, payload)
        assert _accepted_without_the_check(mailbox.mapping_name)
        assert mailbox.take() is None
        assert mailbox.refused_payloads == 1 and mailbox._reader.refused == 1
        assert mailbox.payload_failure["cause"] == cause and mailbox.payload_failure["sequence"] == sequence
        assert _consumed(mailbox.mapping_name) == 0                           # never acknowledged
        assert len(failed) == 1 and failed[0]["cause"] == cause                # the stream reported failed, once
        # The stream stays failed: nothing more is read or reported, whatever is published next.
        assert mailbox.take() is None and mailbox.peek() is None and len(failed) == 1
        assert not mailbox._reader.has_unread()
    finally:
        mailbox.close()
        sender.close()


@pytest.mark.parametrize("case", sorted(_NATIVE_CASES))
def test_a_native_reader_refuses_an_unsupported_slot_at_its_head(case):
    _assert_refused("native", *_bad_slot(case), _NATIVE_CASES[case])


@pytest.mark.parametrize("case,cause", [("native payload", "schema"), ("unknown schema", "schema"),
                                        ("unknown mode code", "mode")])
def test_the_codec_reader_refuses_a_native_or_unknown_slot_at_its_head(case, cause):
    size = spectrum.LAYOUT.size
    schema, mode, payload = {
        "native payload": (spectrum.SCHEMA_ID, 1, bytes(size)),
        "unknown schema": (0x7, 1, frame_codec.encode((1, 1, 0.0, None))),
        "unknown mode code": (frame_codec.CODEC_SCHEMA, 200, frame_codec.encode((1, 1, 0.0, None))),
    }[case]
    _assert_refused("codec", schema, mode, payload, cause)


@pytest.mark.parametrize("mode", [0, *sorted(MODE_CODES.values())])
def test_the_codec_reader_admits_a_codec_slot_of_every_registered_mode(mode, monkeypatch):
    # The product's stream is the codec stream and one refusal fails it for the whole session, so a false refusal is
    # as costly as a missed one: a codec slot stamped with any mode code the writer can stamp (``MODE_CODES``, or 0
    # for none) is admitted and taken. Negative control (audit, 12 Nov): with the code missing from the reader's
    # known set, the same head is refused.
    receiver, sender = Pipe(duplex=False)
    mailbox = PacketMailbox(role="reader", slot_bytes=64 * 1024, payload="codec")
    try:
        mailbox.listen_for_wakes(receiver, on_closed=lambda: None)
        _publish_raw(mailbox.mapping_name, frame_codec.CODEC_SCHEMA, mode, frame_codec.encode((3, 4, 1.0, None)))
        publication = mailbox.take()
        assert publication is not None and publication.generation == 3
        assert mailbox.refused_payloads == 0 and mailbox.payload_failure is None
    finally:
        mailbox.close()
        sender.close()
    if mode:
        monkeypatch.setattr(native_schema, "_KNOWN_MODE_CODES", frozenset(MODE_CODES.values()) - {mode})
        with pytest.raises(native_schema.PayloadRefused):
            native_schema.admit_slot_head(frame_codec.CODEC_SCHEMA, mode, 64, accept="codec")


def test_the_head_check_runs_before_the_payload_is_copied():
    # The reader's admission sees the head of a slot whose payload length is beyond the slot (a copy would be cut
    # short and the old reader counts it torn); the head check refuses it by its size first.
    mailbox = PacketMailbox(role="reader", slot_bytes=4096, payload="native")
    try:
        memory = SharedMemory(name=mailbox.mapping_name)
        writer = FramePacketWriter(memory.buf)
        writer.publish(bytes(spectrum.LAYOUT.size), payload_schema=spectrum.SCHEMA_ID, logical_timestamp=1.0,
                       mode_code=1)
        # The slot's payload_bytes, rewritten beyond the slot (the seqlock still whole).
        from core.visualizer_engine import packet_abi
        base = packet_abi.HEADER_BYTES + writer._latest_slot * 4096
        struct.pack_into("<I", memory.buf, base + 8, 1 << 20)
        writer.release()
        memory.close()
        assert mailbox.take() is None and mailbox.payload_failure["cause"] == "size"
    finally:
        mailbox.close()


@pytest.mark.qt
def test_a_malformed_native_record_is_refused_not_repaired(spectrum_frames):
    record = bytearray(spectrum.encode(spectrum_frames[0]))
    struct.pack_into("<I", record, spectrum.LAYOUT.field("bars_len").offset, MAX_LEVELS + 1)
    with pytest.raises(native_schema.PayloadRefused) as refused:
        spectrum.decode(bytes(record))
    assert refused.value.cause == "record"
    # Negative control: the layout's own unpack (no range check) reads it.
    assert spectrum.LAYOUT.unpack(bytes(record))["bars_len"] == MAX_LEVELS + 1


# ------------------------------------------------------------------------------------------- the writer's stamp

@pytest.mark.qt
def test_the_writer_stamps_the_codec_or_the_native_schema_and_the_native_stream_round_trips(spectrum_frames):
    frame = spectrum_frames[-1]
    for kind, expected in (("codec", frame_codec.CODEC_SCHEMA), ("native", spectrum.SCHEMA_ID)):
        mailbox = PacketMailbox(slot_bytes=64 * 1024, payload=kind)
        try:
            mailbox.publish(frame, generation=frame.runtime_generation, activation_id=frame.activation_id)
            reader = FramePacketReader(mailbox._memory.buf)     # a second, unchecked view of the slot
            try:
                assert reader.read_latest().payload_schema == expected
            finally:
                reader.release()
            taken = mailbox.take()
            if kind == "native":
                assert repr(taken.state) == repr(spectrum.project(_tagged(frame)))
                assert taken.generation == frame.runtime_generation and taken.activation_id == frame.activation_id
            else:
                assert repr(taken.state) == repr(frame)
            assert mailbox.refused_payloads == 0 and _consumed(mailbox.mapping_name) > 0
        finally:
            mailbox.close()


def test_a_native_writer_refuses_a_mode_without_a_native_schema():
    from widgets.spotify_visualizer.render_state import (
        OscilloscopeFrame,
        VisualizerCommonState,
        VisualizerLogicalFrame,
    )

    frame = VisualizerLogicalFrame(
        runtime_generation=1, engine_generation=1, activation_id=1, source_generation=1, source_activation_id=1,
        mode_id="oscilloscope", playing=True, logical_timestamp=1.0, source_timestamp=None, changed=True,
        present_frame=True, mode_reveal_ready=True, common=VisualizerCommonState(bars=(), bar_count=0),
        mode_state=OscilloscopeFrame())
    mailbox = PacketMailbox(slot_bytes=64 * 1024, payload="native")
    try:
        with pytest.raises(native_schema.NativeSchemaError):
            mailbox.publish(frame, generation=1, activation_id=1)
        assert mailbox.take() is None and mailbox.refused_payloads == 0
    finally:
        mailbox.close()
    # Control: the codec stream carries the same frame.
    mailbox = PacketMailbox(slot_bytes=64 * 1024)
    try:
        mailbox.publish(frame, generation=1, activation_id=1)
        assert mailbox.take().state == frame
    finally:
        mailbox.close()


# ------------------------------------------------------------------------------- the owner's failure edge

@pytest.mark.qt
def test_a_refused_payload_reaches_the_owner_as_the_sessions_end(qt_app):
    from widgets.spotify_visualizer.engine_worker_link import EngineWorkerLink

    lost = []
    link = EngineWorkerLink(object(), on_lost=lambda _link, reason: lost.append(reason))
    receiver, sender = Pipe(duplex=False)
    mailbox = PacketMailbox(role="reader", slot_bytes=64 * 1024)
    link._mailbox = mailbox
    try:
        mailbox.listen_for_wakes(receiver, on_closed=link._session_ended)
        _publish_raw(mailbox.mapping_name, spectrum.SCHEMA_ID, 1, bytes(spectrum.LAYOUT.size))
        assert mailbox.take() is None
        for _ in range(20):
            qt_app.processEvents()
            if lost:
                break
        assert len(lost) == 1 and lost[0].startswith("frame payload refused (schema")
        assert link.payload_failure_report["cause"] == "schema"
    finally:
        link.close()
        sender.close()


@pytest.mark.qt
def test_a_refused_payload_fails_closed_without_recovery_or_in_process_fallback(qt_app, monkeypatch, caplog):
    # N2.3's leftover (N2.5 box 9): a refusal means the writer and the reader disagree on the stream's contract, which
    # neither a reconfigure nor the in-process path cures, so the owner holds the activation failed as the capacity
    # violation does (``test_capacity_violation_fails_closed_without_recovery_or_in_process_fallback``). The real
    # owner on an in-process session whose writer stamps Spectrum's native schema on the codec stream this owner reads.
    # Negative control (seen 14 Nov): the owner before the change took the session's failure path (a recovery).
    from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor, _pump
    from tools.visualizer_replay import owner_worker_gate as gate
    from tools.visualizer_replay.live_engine_gate import paced_pcm
    from widgets.spotify_visualizer import engine_worker_link

    supervisor = _InProcessSupervisor()
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=supervisor, cadence="thread")
    attempts: list[str] = []
    try:
        pcm, rate = paced_pcm(1.0)
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm, pcm_rate=rate):
            owner = rig.build()
            link = owner._worker
            monkeypatch.setattr(owner, "_fall_back_in_process", lambda *a, **k: attempts.append("fallback"))
            monkeypatch.setattr(owner, "_on_engine_worker_failed", lambda *a, **k: attempts.append("recovery"))
            supervisor.worker._session.mailbox._payload = "native"      # the writer's side of the disagreement
            _pump(rig, 3.0, until=lambda: owner._mode_transition_phase == "failed" or bool(attempts))
        assert link.payload_failure_report is not None and link.payload_failure_report["cause"] == "schema"
        assert owner._mode_transition_phase == "failed" and not attempts, attempts
        assert link.closed or link._stopping                                                 # retired
        assert "Frame payload REFUSED" in caplog.text
    finally:
        rig.close()
        supervisor.close()
        engine_worker_link.reset_run_state_for_testing()


@pytest.mark.qt
@pytest.mark.parametrize("payload", ("native", "codec"))
def test_a_real_worker_whose_payload_the_owner_refuses_ends_its_session(qt_app, monkeypatch, payload):
    # The refusal path end to end with a real worker process (the test above writes the slot in process): the REAL
    # owner (the host binding's rig, no window shown) on a real ``WorkerType.VISUALIZER`` process fed recorded PCM, whose
    # session writes Spectrum's native schema; this process's reader is the Python codec reader, which refuses the
    # first slot it reads at its head (D2: one consumer per stream, a native payload on a codec stream). The refused
    # slot is never acknowledged, the stream fails, the link reports the session's end with the refusal as its reason,
    # and the owner fails closed (N2.5 box 9: no reconfigure, no fall back in process; the session retired and the
    # activation held failed, as a capacity violation is). Control: the same worker writing the codec is read, never
    # refused, and stays the owner's worker.
    import os

    from core.process.supervisor import ProcessSupervisor
    from core.process.types import WorkerType
    from core.visualizer_engine.engine_worker import EngineSession, visualizer_worker_main
    from tests.test_visualizer_owner_engine_worker import _pump
    from tools.visualizer_replay import owner_worker_gate as gate
    from tools.visualizer_replay.live_engine_gate import paced_pcm
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    def _device(_config=None):
        raise AssertionError("a test opened an audio device")

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", _device)
    monkeypatch.setattr(EngineSession, "LIVE_EDGE_TIMEOUT_S", 10.0)
    engine_worker_link.reset_run_state_for_testing()
    refusals: list[dict] = []
    refuse = PacketMailbox._refuse
    supervisor = ProcessSupervisor()

    def recording_refusal(self, refusal):
        # What the mapping says at the refusal (the reader has acknowledged nothing), and who wrote the slot.
        worker = supervisor._workers.get(WorkerType.VISUALIZER)
        refusals.append({"cause": refusal.cause, "consumed": struct.unpack_from("<Q", self._reader._view, 40)[0],
                         "reason": str(refusal), "writer_pid": getattr(worker, "pid", None)})
        return refuse(self, refusal)

    lost: list[str] = []
    on_lost = QuickDisplayVisualizerOwner._on_engine_worker_lost

    def recording_lost(self, link, reason):
        lost.append(str(reason))
        return on_lost(self, link, reason)

    monkeypatch.setattr(PacketMailbox, "_refuse", recording_refusal)
    monkeypatch.setattr(QuickDisplayVisualizerOwner, "_on_engine_worker_lost", recording_lost)
    pcm, rate = paced_pcm(3.0)
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    assert supervisor.start(WorkerType.VISUALIZER)
    rig = gate.OwnerRig("spectrum", worker=True, supervisor=supervisor, cadence="thread")
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm, pcm_rate=rate, payload=payload):
            owner = rig.build()                     # a refusal never falls back in process, even inside the settle
            link = owner._worker
            if payload == "codec":
                first = owner._worker
                assert first is not None
                worker_pid = supervisor._workers[WorkerType.VISUALIZER].pid
                assert worker_pid and worker_pid != os.getpid()                     # a real process
                _pump(rig, 2.0, until=lambda: first.configured and len(rig.published) > 30)
                presented = len(rig.published)
                _pump(rig, 0.5)
                assert not refusals and not lost and owner._worker is first and first.configured
                assert first.mailbox.refused_payloads == 0 and len(rig.published) > presented
                return
            _pump(rig, 30.0, until=lambda: bool(lost) and owner._mode_transition_phase == "failed")
        assert refusals, lost
        assert all(r["writer_pid"] and r["writer_pid"] != os.getpid() for r in refusals), refusals
        assert all(r["cause"] == "schema" and r["consumed"] == 0 for r in refusals), refusals
        assert "on a stream the Python codec consumes" in refusals[0]["reason"]
        assert len(lost) == 1 and lost[0].startswith("frame payload refused (schema, sequence "), lost
        # Failed closed: the same (retired) session, held failed; no recovery took the run's slot and nothing in
        # process asked for an engine.
        assert owner._worker is link and (link.closed or link._stopping)
        assert owner._mode_transition_phase == "failed" and owner._worker_failures == 0
        assert not engine_worker_link.worker_disabled_for_run()
    finally:
        rig.close()
        supervisor.shutdown()
        engine_worker_link.reset_run_state_for_testing()
