"""Native core P2: the frame packet ABI (Docs/Future_Work/Native_Core_P2_Engine_Design.md).

Newest state only (never a queue or catch-up replay), torn writes never accepted, protected edges survive skipped
frames until a read acknowledges them, a mismatched ABI refused, and the named mapping works across processes."""
import multiprocessing as mp
import struct
import uuid

import pytest

from core.visualizer_engine import packet_abi as abi

SLOT = 256


def fresh(**identity):
    buffer = bytearray(abi.mapping_bytes(SLOT))
    abi.initialise(buffer, slot_bytes=SLOT, **{'runtime_generation': 3, 'engine_generation': 5, 'activation_id': 7,
                                               'mode_code': 2, **identity})
    return buffer, abi.FramePacketWriter(buffer), abi.FramePacketReader(buffer)


def test_a_published_frame_reads_back_exactly():
    buffer, writer, reader = fresh()
    assert reader.identity == (3, 5, 7) and reader.mode_code == 2
    sequence = writer.publish(b'payload\x00\xff', payload_schema=9, logical_timestamp=12.5, source_timestamp=None,
                              flags=abi.FLAG_CHANGED | abi.FLAG_PLAYING, protected_edges=0b100)
    packet = reader.read_latest()
    assert packet == abi.FramePacket(sequence, 9, 12.5, None, abi.FLAG_CHANGED | abi.FLAG_PLAYING, 0b100,
                                     b'payload\x00\xff')
    assert reader.read_latest() is None                 # nothing new: the caller keeps its frame


def test_the_reader_takes_the_newest_frame_never_a_backlog():
    buffer, writer, reader = fresh()
    for index in range(7):
        writer.publish(bytes([index])*5, payload_schema=1, logical_timestamp=float(index), source_timestamp=index+.5)
    packet = reader.read_latest()
    assert packet.payload == bytes([6])*5 and packet.logical_timestamp == 6. and packet.source_timestamp == 6.5
    assert reader.read_latest() is None


def test_a_torn_slot_is_never_accepted():
    buffer, writer, reader = fresh()
    writer.publish(b'first', payload_schema=1, logical_timestamp=1.)
    assert reader.read_latest().payload == b'first'
    sequence = writer.publish(b'second', payload_schema=1, logical_timestamp=2.)
    # Find the slot just written and tear it: sequence_end disagrees, as while the writer is still filling it.
    for slot in range(abi.SLOT_COUNT):
        base = abi.HEADER_BYTES+slot*SLOT
        if struct.unpack_from('<Q', buffer, base)[0] == sequence:
            struct.pack_into('<Q', buffer, base+SLOT-8, sequence-1)
    assert reader.read_latest() is None and reader.torn_reads == 1    # rejected: the previous frame stays shown
    # Negative control: the same slot made whole again is accepted.
    for slot in range(abi.SLOT_COUNT):
        base = abi.HEADER_BYTES+slot*SLOT
        if struct.unpack_from('<Q', buffer, base)[0] == sequence:
            struct.pack_into('<Q', buffer, base+SLOT-8, sequence)
    assert reader.read_latest().payload == b'second'


class _InterleavedStruct:
    """A struct whose read of the slot under test lets the writer start overwriting that slot right after it."""

    def __init__(self, real, on_read):
        self._real, self._on_read = real, on_read
        self.size = real.size

    def unpack_from(self, buffer, offset=0):
        value = self._real.unpack_from(buffer, offset)
        self._on_read(offset)
        return value

    def pack_into(self, *args):
        return self._real.pack_into(*args)


def test_a_write_begun_while_the_reader_copies_is_never_accepted(monkeypatch):
    # The writer comes round to the slot being read (two frames later) and starts the next frame into it while the
    # reader copies the payload: begin goes odd and the payload changes after the reader has read the slot head (and
    # sequence_end, still the old value). Only the final sequence_begin re-read can see it (audit C2; checkpoint
    # audit 2, A2-H1: an earlier version of this test tore before the head read, which the head check alone caught).
    buffer, writer, reader = fresh()
    sequence = writer.publish(b'AAAAAAAA', payload_schema=1, logical_timestamp=1.)
    base = next(abi.HEADER_BYTES+slot*SLOT for slot in range(abi.SLOT_COUNT)
                if struct.unpack_from('<Q', buffer, abi.HEADER_BYTES+slot*SLOT)[0] == sequence)
    state = {"torn": False}

    def writer_starts_after_the_head(offset):
        if offset != base or state["torn"]:
            return
        state["torn"] = True
        struct.pack_into('<Q', buffer, base, sequence+5)                        # begin odd: a new frame starts
        buffer[base+abi.SLOT_PAYLOAD_OFFSET:base+abi.SLOT_PAYLOAD_OFFSET+8] = b'DDDDDDDD'

    monkeypatch.setattr(abi, "_SLOT_HEAD", _InterleavedStruct(abi._SLOT_HEAD, writer_starts_after_the_head))
    assert reader.read_latest() is None and state["torn"] and reader.torn_reads == 1


def test_the_final_sequence_begin_read_is_what_rejects_a_mid_copy_write(monkeypatch):
    # Negative control for the test above: a reader that skips the final sequence_begin re-read accepts the torn
    # copy under the same interleaving, so that re-read is what the test proves.
    import inspect
    import textwrap

    source = textwrap.dedent(inspect.getsource(abi.FramePacketReader.read_latest))
    assert source.count("begin = _U64.unpack_from(view, base)[0]") == 1
    weakened = source.replace("begin = _U64.unpack_from(view, base)[0]", "begin = head")
    namespace = dict(vars(abi))
    exec(compile(weakened, "<weakened read_latest>", "exec"), namespace)
    buffer, writer, reader = fresh()
    sequence = writer.publish(b'AAAAAAAA', payload_schema=1, logical_timestamp=1.)
    base = next(abi.HEADER_BYTES+slot*SLOT for slot in range(abi.SLOT_COUNT)
                if struct.unpack_from('<Q', buffer, abi.HEADER_BYTES+slot*SLOT)[0] == sequence)
    torn = {"done": False}

    def tear(offset):
        if offset == base and not torn["done"]:
            torn["done"] = True
            struct.pack_into('<Q', buffer, base, sequence+5)
            buffer[base+abi.SLOT_PAYLOAD_OFFSET:base+abi.SLOT_PAYLOAD_OFFSET+8] = b'DDDDDDDD'

    namespace["_SLOT_HEAD"] = _InterleavedStruct(abi._SLOT_HEAD, tear)
    packet = namespace["read_latest"](reader)
    assert packet is not None and packet.payload == b'DDDDDDDD'       # the weakened reader takes the torn bytes


def test_protected_edges_survive_skipped_frames_until_acknowledged():
    buffer, writer, reader = fresh()
    writer.publish(b'a', payload_schema=1, logical_timestamp=1., protected_edges=0b001)   # never read on its own
    writer.publish(b'b', payload_schema=1, logical_timestamp=2., protected_edges=0b010)
    writer.publish(b'c', payload_schema=1, logical_timestamp=3.)
    packet = reader.read_latest()
    assert packet.payload == b'c' and packet.protected_edge_mask == 0b011   # both skipped edges still carried
    reader.acknowledge(packet.sequence)
    writer.publish(b'd', payload_schema=1, logical_timestamp=4.)
    assert reader.read_latest().protected_edge_mask == 0                   # delivered: no longer carried


def test_the_writer_never_overwrites_the_newest_slot():
    buffer, writer, reader = fresh()
    slots = []
    for index in range(6):
        sequence = writer.publish(b'x', payload_schema=1, logical_timestamp=float(index))
        slots.append(next(slot for slot in range(abi.SLOT_COUNT)
                          if struct.unpack_from('<Q', buffer, abi.HEADER_BYTES+slot*SLOT)[0] == sequence))
    assert all(a != b for a, b in zip(slots, slots[1:]))
    # A writer re-attached to the same mapping continues the sequence and skips the newest slot too.
    again = abi.FramePacketWriter(buffer)
    sequence = again.publish(b'y', payload_schema=1, logical_timestamp=9.)
    assert sequence == 2*7 and reader.read_latest().payload == b'y'


def test_a_mapping_of_another_abi_is_refused():
    buffer, _writer, _reader = fresh()
    for offset, value in ((0, b'XXXX'), (4, struct.pack('<H', abi.ABI_VERSION+1))):
        broken = bytearray(buffer)
        broken[offset:offset+len(value)] = value
        with pytest.raises(abi.PacketAbiError):
            abi.FramePacketReader(broken)
        with pytest.raises(abi.PacketAbiError):
            abi.FramePacketWriter(broken)


def test_an_oversized_payload_is_refused_and_nothing_is_published():
    buffer, writer, reader = fresh()
    with pytest.raises(ValueError):
        writer.publish(bytes(writer.capacity+1), payload_schema=1, logical_timestamp=1.)
    assert reader.read_latest() is None
    writer.publish(bytes(writer.capacity), payload_schema=1, logical_timestamp=1.)
    assert len(reader.read_latest().payload) == writer.capacity


def _write_in_child(name, count):
    from multiprocessing.shared_memory import SharedMemory
    memory = SharedMemory(name=name)
    try:
        writer = abi.FramePacketWriter(memory.buf)
        for index in range(count):
            writer.publish(index.to_bytes(4, 'little')*8, payload_schema=1, logical_timestamp=float(index))
        writer.release()
    finally:
        memory.close()


def test_the_named_mapping_carries_frames_across_processes():
    memory = abi.create_frame_mapping(generation=4, slot_bytes=SLOT, engine_generation=1, activation_id=2,
                                      mode_code=3, token=uuid.uuid4().hex[:8])
    try:
        child = mp.get_context('spawn').Process(target=_write_in_child, args=(memory.name, 50))
        child.start()
        child.join(60)
        assert child.exitcode == 0
        reader = abi.FramePacketReader(memory.buf)
        packet = reader.read_latest()
        assert packet.payload == (49).to_bytes(4, 'little')*8 and packet.logical_timestamp == 49.
        assert reader.identity == (4, 1, 2) and reader.mode_code == 3
        reader.release()
    finally:
        memory.close()
        memory.unlink()


def test_each_slot_carries_its_own_identity_under_the_seqlock():
    # ABI 2 (checkpoint audit 3, A3-M4): the frame's identity lives in its slot's head, so an in-place mode switch
    # never relabels a slot a reader is validating; -1 ("none") is stored as 0xFFFFFFFF; plain struct reads it at 40.
    buffer, writer, reader = fresh()
    sequence = writer.publish(b'a', payload_schema=1, logical_timestamp=1., runtime_generation=11,
                              engine_generation=-1, activation_id=4, mode_code=abi.MODE_CODES['sphere'])
    packet = reader.read_latest()
    assert (packet.runtime_generation, packet.engine_generation, packet.activation_id, packet.mode_code) == (
        11, 0xFFFFFFFF, 4, abi.MODE_CODES['sphere'])
    base = next(abi.HEADER_BYTES+slot*SLOT for slot in range(abi.SLOT_COUNT)
                if struct.unpack_from('<Q', buffer, abi.HEADER_BYTES+slot*SLOT)[0] == sequence)
    assert struct.unpack_from('<IIII', buffer, base+40) == (11, 0xFFFFFFFF, 4, abi.MODE_CODES['sphere'])
    assert abi.SLOT_PAYLOAD_OFFSET % 16 == 0 and struct.calcsize('<QIIddIIIIII') <= abi.SLOT_PAYLOAD_OFFSET
    # The header keeps the configure-time identity.
    writer.write_identity(runtime_generation=11, engine_generation=2, activation_id=3, mode_code=5)
    assert reader.read_identity() == (11, 2, 3, 5)


def test_every_registered_mode_has_one_stable_header_code():
    # A new mode fails here until it is given the next code (codes are append-only; 0 means none).
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors

    modes = {d.mode_id for d in iter_all_visualizer_mode_descriptors()}
    assert modes <= set(abi.MODE_CODES)
    codes = list(abi.MODE_CODES.values())
    assert len(set(codes)) == len(codes) and 0 not in codes and abi.mode_code(None) == 0
    with pytest.raises(KeyError):
        abi.mode_code('not_a_mode')


#: The ABI's mode codes as of ABI 2 (C readers carry the same table): an ABI constant, not a user-editable value.
#: Append-only: an entry here never changes or goes away, and a new mode only adds after these (checkpoint audit 4,
#: A4-L2). Adding a mode extends this list in the same change.
_KNOWN_MODE_CODES = (
    ("spectrum", 1), ("oscilloscope", 2), ("bubble", 3), ("devcurve", 4), ("sphere", 5), ("extruded_spectrum", 6),
    ("shockwave_grid", 7), ("extruded_bubble", 8), ("waveform_ribbon", 9),
)


def test_mode_codes_are_append_only():
    table = list(abi.MODE_CODES.items())
    assert table[:len(_KNOWN_MODE_CODES)] == list(_KNOWN_MODE_CODES)        # no renumbering, reordering or removal
    known_max = max(code for _mode, code in _KNOWN_MODE_CODES)
    appended = [code for _mode, code in table[len(_KNOWN_MODE_CODES):]]
    assert appended == sorted(appended) and all(code > known_max for code in appended)   # new codes only after


def _identity(activation, mode="spectrum"):
    return {"runtime_generation": 3, "engine_generation": activation, "activation_id": activation,
            "mode_code": abi.MODE_CODES[mode]}


def test_a_protected_edge_never_crosses_into_another_activations_slot():
    # A4-M4: an edge published under activation N and not yet read is carried into later slots of activation N only;
    # after an in-place switch the reader's first slot of activation N+1 carries none of N's edges.
    buffer, writer, reader = fresh()
    writer.publish(b'a', payload_schema=1, logical_timestamp=1., protected_edges=0b001, **_identity(4))
    writer.publish(b'b', payload_schema=1, logical_timestamp=2., protected_edges=0b100, **_identity(5, "sphere"))
    writer.publish(b'c', payload_schema=1, logical_timestamp=3., **_identity(5, "sphere"))
    packet = reader.read_latest()
    assert packet.payload == b'c' and packet.activation_id == 5 and packet.protected_edge_mask == 0b100
    # Control: within one activation the unread edge is carried (the survival contract still holds).
    buffer, writer, reader = fresh()
    writer.publish(b'a', payload_schema=1, logical_timestamp=1., protected_edges=0b001, **_identity(4))
    writer.publish(b'c', payload_schema=1, logical_timestamp=3., **_identity(4))
    assert reader.read_latest().protected_edge_mask == 0b001


class _StoreLog:
    """A struct whose stores are logged as (offset, size) as they are made."""

    def __init__(self, real, log):
        self._real, self._log = real, log
        self.size = real.size

    def unpack_from(self, *args):
        return self._real.unpack_from(*args)

    def pack_into(self, buffer, offset, *values):
        self._log.append((offset, self._real.size))
        return self._real.pack_into(buffer, offset, *values)


def test_the_odd_sequence_begin_is_its_own_store_before_any_other_slot_head_field(monkeypatch):
    # A4-L1: the odd begin is stored alone (8 bytes at the slot base) before the rest of the head, so the identity can
    # never become visible ahead of the begin change (a combined pack zero-fills the whole head in one C store).
    buffer, writer, reader = fresh()
    log = []
    for name, value in list(vars(abi).items()):
        if name.startswith("_") and isinstance(value, struct.Struct):
            monkeypatch.setattr(abi, name, _StoreLog(value, log))
    sequence = writer.publish(b'x', payload_schema=1, logical_timestamp=1., **_identity(4))
    base = next(abi.HEADER_BYTES+slot*SLOT for slot in range(abi.SLOT_COUNT)
                if struct.unpack_from('<Q', buffer, abi.HEADER_BYTES+slot*SLOT)[0] == sequence)
    head = [(offset, size) for offset, size in log if base <= offset < base+abi.SLOT_PAYLOAD_OFFSET]
    assert head[0] == (base, 8)                                   # the odd begin, alone, first
    assert all(offset >= base+8 for offset, _size in head[1:-1])  # then the head after it (identity included) ...
    assert head[-1] == (base, 8)                                  # ... and the even begin last
    assert reader.read_latest().activation_id == 4                # the C2 reader still accepts the whole slot
