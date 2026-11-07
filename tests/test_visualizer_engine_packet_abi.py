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
