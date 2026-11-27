"""N5.6 "Native record and route": Extruded Bubble's D3 geometry arena (main-process owner, worker writer, the
projection that names only whole keys) and the drift solver's compute stream.

Each check runs against the real code and, as its negative control, against a copy of the module with the one rule it
proves broken (``_mutated``): the check must fail there, so it can see the defect it guards."""
import re
import struct
import sys
import types
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import core.visualizer_engine.extruded_bubble_native_schema as schema_module
import core.visualizer_engine.geometry_arena as arena_module
import core.visualizer_engine.packet_mailbox as mailbox_module
from core.visualizer_engine.extruded_bubble_native_schema import (
    DRIFT_RECORD_ENTRIES, DRIFT_STREAM_FLOATS, DriftRecordProjector, DriftSteps,
)
from core.visualizer_engine.geometry_arena import (
    BANK_HEADER_BYTES, GeometryArenaError, GeometryArenaOwner, GeometryArenaWriter, bank_offset,
)
from core.visualizer_engine.native_schema import MAX_RECORD_BYTES, NativeLayout, NativeSchemaError, native_schema_id
from core.visualizer_engine.packet_abi import MODE_CODES
from widgets.spotify_visualizer.extruded_bubble_drift_log import (
    CHAIN_GEOMETRY_BYTES, FAMILIES, KNOT_DECISION_BYTES, STEP_FLOATS, STEP_HISTORY, STEP_INDEX, DriftFamily,
    knot_starts,
)
from widgets.spotify_visualizer.extruded_bubble_material_paths import CHAIN_PATHS
from widgets.spotify_visualizer.render_state import ExtrudedBubbleFrame

ROOT = Path(__file__).resolve().parents[1]
CHAINS = FAMILIES.index("chains")


def _mutated(module, *edits):
    """A copy of ``module`` with each (old, new) applied once: a negative control's broken rule."""
    source = Path(module.__file__).read_text(encoding="utf-8")
    for old, new in edits:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    copy = types.ModuleType(module.__name__ + "_control")
    copy.__file__ = module.__file__
    sys.modules[copy.__name__] = copy
    try:
        exec(compile(source, module.__file__, "exec"), copy.__dict__)
    finally:
        sys.modules.pop(copy.__name__, None)
    return copy


def _family(revision, *, capacity=2, rebase_from=0, first=1, fill=1):
    return DriftFamily("chains", revision, rebase_from, first, capacity,
                       bytes([fill % 251 + 1]) * (CHAIN_GEOMETRY_BYTES * capacity))


def _state(*families, engine=2, activation=3, serials=(1,)):
    return SimpleNamespace(mode_state=_frame(serials, *families), engine_generation=engine, activation_id=activation)


def _frame(serials, *families, knot_counts=None, seed=0):
    rng = np.random.default_rng(seed)
    rows = rng.uniform(-4.0, 4.0, (len(serials), STEP_FLOATS))
    rows[:, STEP_INDEX["serial"]] = serials
    counts = [0] * len(serials) if knot_counts is None else list(knot_counts)
    rows[:, STEP_INDEX["chain_rows"]] = counts
    knots = rng.integers(0, 256, sum(counts) * KNOT_DECISION_BYTES, dtype=np.uint8).tobytes()
    return ExtrudedBubbleFrame(drift_families=families, drift_steps=rows.astype("<f8").tobytes(), drift_knots=knots)


@pytest.fixture
def arena():
    owner = GeometryArenaOwner(families=len(FAMILIES), bank_bytes=CHAIN_GEOMETRY_BYTES * 4)
    writers = []

    def attach(module=arena_module):
        writer = module.GeometryArenaWriter(owner.name, families=FAMILIES)
        writers.append(writer)
        return writer
    yield owner, attach
    for writer in writers:
        writer.close()
    owner.close()


def _publish(writer, state, consumed, sequence):
    writer.before_publish(state, consumed)
    writer.published(sequence)


def _bank_keys(owner):
    return [arena_module._bank_key(owner._memory.buf, bank_offset(CHAINS, b, owner.bank_bytes))[1][4:]
            for b in range(2)]


# ------------------------------------------------------------------------------------------ sub-box 1: the arena

@dataclass(frozen=True)
class _Frame:                      # a stand-in with a logical frame's identity fields, through the generic codec
    value: float
    mode_id: str = "spectrum"
    engine_generation: int = 1
    protected_edges: tuple = field(default=())
    logical_timestamp: float = 0.0


def _check_written_before_the_slot(monkeypatch, module):
    from core.visualizer_engine import frame_codec
    ids, layouts, frozen = frame_codec._types()
    monkeypatch.setitem(ids, _Frame, len(layouts))
    monkeypatch.setattr(frame_codec, "_tables", (ids, list(layouts) + [(_Frame, tuple(_Frame.__dataclass_fields__))],
                                                 frozen))
    reader = module.PacketMailbox(slot_bytes=64 * 1024, role="reader")
    writer = module.PacketMailbox(role="writer", attach=reader.mapping_name)
    seen = []

    class Recorder:
        def before_publish(self, state, consumed):
            peeked = reader.peek()
            seen.append(("before", state.value, None if peeked is None else peeked.state.value, consumed))

        def published(self, sequence):
            seen.append(("published", reader.peek().state.value, sequence))

    try:
        writer.set_geometry_writer(Recorder())
        writer.publish(_Frame(1.0), generation=4)
        reader.take()
        writer.publish(_Frame(2.0), generation=4)
        # Each frame's keys are written before the reader can see its slot, and the sequence the bank is live through
        # is the slot's own; the consumed sequence handed to the writer is the reader's take of frame 1.
        assert seen[0][:3] == ("before", 1.0, None) and seen[1][:2] == ("published", 1.0)
        assert seen[2][:3] == ("before", 2.0, None) and seen[2][3] == seen[1][2]
        assert seen[3][:2] == ("published", 2.0) and seen[3][2] > seen[1][2]
        with pytest.raises(TypeError):
            writer.set_geometry_writer(object())
    finally:
        writer.close()
        reader.close()


def test_each_frame_writes_its_keys_before_the_slot_that_names_them(monkeypatch):
    _check_written_before_the_slot(monkeypatch, mailbox_module)
    late = _mutated(mailbox_module,
                    ("                geometry.before_publish(state, consumed)\n", "                pass\n"),
                    ("                geometry.published(sequence)",
                     "                geometry.before_publish(state, consumed); geometry.published(sequence)"))
    with pytest.raises(AssertionError):
        _check_written_before_the_slot(monkeypatch, late)


class _Probe:
    """Geometry bytes that see the bank's sequence while they are copied (the seqlock's open write)."""

    def __init__(self, data, memory, at):
        self.data, self.memory, self.at, self.during = data, memory, at, None

    def __len__(self):
        return len(self.data)

    def __buffer__(self, flags):
        self.during = struct.unpack_from("<I", self.memory.buf, self.at)[0]
        return memoryview(self.data)


def _check_seqlock(arena, module):
    owner, attach = arena
    writer = attach(module)
    descriptor = _family(5)
    probe = _Probe(descriptor.geometry, owner._memory, bank_offset(CHAINS, 0, owner.bank_bytes))
    key = writer.key_for("chains", descriptor, 2, 3)
    assert not owner.holds(key)
    _publish(writer, _state(replace(descriptor, geometry=probe)), 0, 1)
    after = struct.unpack_from("<I", owner._memory.buf, probe.at)[0]
    assert probe.during % 2 == 1 and after % 2 == 0 and after > probe.during      # odd while copied, then even
    assert owner.holds(key)
    start = probe.at + BANK_HEADER_BYTES
    assert bytes(owner._memory.buf[start:start + len(descriptor.geometry)]) == descriptor.geometry
    struct.pack_into("<I", owner._memory.buf, probe.at, after | 1)                 # a torn bank is never held
    assert not owner.holds(key)


def test_a_bank_is_odd_while_its_geometry_is_copied_and_whole_after(arena):
    _check_seqlock(arena, arena_module)


def test_control_a_bank_marked_whole_before_its_copy_is_seen(arena):
    early = _mutated(arena_module, ("_SEQUENCE.pack_into(view, at, (sequence + 1) | 1)            # odd",
                                    "_SEQUENCE.pack_into(view, at, ((sequence + 1) | 1) + 1)      # odd"))
    with pytest.raises(AssertionError):
        _check_seqlock(arena, early)


def _check_reuse_after_ack(arena, module):
    owner, attach = arena
    writer = attach(module)
    k1, k2, k3 = (_family(r) for r in (11, 12, 13))
    _publish(writer, _state(k1), 0, 1)
    _publish(writer, _state(k2), 0, 2)                  # the empty bank
    # Both banks live: k1's last frame (1) is not yet acknowledged past, k2 is the newest named key. k3 is deferred and
    # the frame keeps naming k2 (its last published key).
    _publish(writer, _state(k3), 1, 3)
    assert writer.deferred == 1 and _bank_keys(owner) == [(11, 2), (12, 2)]
    assert owner.holds(writer.key_for("chains", k1, 2, 3)) and owner.holds(writer.key_for("chains", k2, 2, 3))
    # The reader took frame 2 (a successor with another key): k1's bank is reused.
    _publish(writer, _state(k3), 2, 4)
    assert writer.deferred == 1 and _bank_keys(owner) == [(13, 2), (12, 2)]


def test_a_bank_is_reused_only_after_a_successor_naming_another_key_is_taken(arena):
    _check_reuse_after_ack(arena, arena_module)


def test_control_a_bank_reused_before_its_successor_is_taken_is_seen(arena):
    eager = _mutated(arena_module, ("if bank.key != current and int(consumed) > bank.last_named:",
                                    "if bank.key != current:"))
    with pytest.raises(AssertionError):
        _check_reuse_after_ack(arena, eager)


def _check_predecessor_kept(arena, module):
    owner, attach = arena
    writer = attach(module)
    k0, k1 = _family(20), _family(21)
    k2 = _family(22, rebase_from=21)
    _publish(writer, _state(k0), 0, 1)                  # bank 0
    _publish(writer, _state(k1), 0, 2)                  # bank 1
    _publish(writer, _state(k2), 5, 3)                  # k0's bank: k2 rebases from k1, which stays whole
    assert _bank_keys(owner) == [(22, 2), (21, 2)] and owner.holds(writer.key_for("chains", k1, 2, 3))
    # Every bank acknowledged: a new key never takes the bank of the key the newest frame names.
    _publish(writer, _state(_family(23)), 9, 4)
    assert _bank_keys(owner) == [(22, 2), (23, 2)] and owner.holds(writer.key_for("chains", k2, 2, 3))


def test_the_named_key_and_a_rebase_predecessor_stay_whole(arena):
    _check_predecessor_kept(arena, arena_module)


def test_control_overwriting_the_named_key_is_seen(arena):
    careless = _mutated(arena_module, ("if bank.key != current and int(consumed) > bank.last_named:",
                                       "if int(consumed) > bank.last_named:"))
    with pytest.raises(AssertionError):
        _check_predecessor_kept(arena, careless)


def _check_deferred_lineage(arena, projector_held):
    owner, attach = arena
    writer = attach()
    projector = DriftRecordProjector(writer.namespace, 2, 3)

    def frame(descriptor, consumed, sequence):
        state = _state(descriptor, serials=(sequence,))
        _publish(writer, state, consumed, sequence)
        held = owner.holds if projector_held else None
        return {k: v for k, v in projector.project(state.mode_state, held=held)[0].items() if k.startswith("chains_")}

    a = frame(_family(31, first=1), 0, 1)
    b = frame(_family(32, rebase_from=31, first=2), 0, 2)
    deferred = frame(_family(33, rebase_from=32, first=3), 1, 3)
    # Both banks live: the projection keeps the family at its last published revision (key, epoch, rebase, birth).
    assert writer.deferred == 1 and deferred == b and b["chains_rebase_from_epoch"] == a["chains_epoch"]
    landed = frame(_family(33, rebase_from=32, first=3), 2, 4)
    assert owner.holds(arena_module.key_of_words(landed["chains_geometry_key"]))
    assert landed["chains_epoch"] == b["chains_epoch"] + 1 and landed["chains_rebase_from_epoch"] == b["chains_epoch"]


def test_a_deferred_key_keeps_the_projection_at_its_last_published_revision(arena):
    _check_deferred_lineage(arena, True)


def test_control_naming_a_key_the_arena_does_not_hold_is_seen(arena):
    with pytest.raises(AssertionError):
        _check_deferred_lineage(arena, False)


def _check_retirement(arena, module):
    owner, attach = arena
    writer = attach(module)
    _publish(writer, _state(_family(40)), 0, 1)         # bank 0
    _publish(writer, _state(_family(41)), 0, 2)         # bank 1
    _publish(writer, _state(_family(42)), 2, 3)         # bank 0 again (40's successor was taken)
    _publish(writer, _state(), 3, 4)                    # the family retired: no key named
    # Frame 4 taken: the retired family's last key (42) is nobody's lineage, so its bank is the first free one.
    _publish(writer, _state(_family(43)), 4, 5)
    assert writer.deferred == 0 and _bank_keys(owner) == [(43, 2), (41, 2)]
    _publish(writer, _state(_family(44)), 5, 6)
    assert writer.deferred == 0 and _bank_keys(owner) == [(43, 2), (44, 2)]


def test_a_retired_family_frees_its_banks_and_the_closed_arena_is_gone(arena):
    _check_retirement(arena, arena_module)
    owner = schema_module.open_stream_arena(0x7A11, CHAIN_GEOMETRY_BYTES)
    assert schema_module.stream_arena(0x7A11) is owner
    with pytest.raises(NativeSchemaError):
        schema_module.open_stream_arena(0x7A11, CHAIN_GEOMETRY_BYTES)
    name = owner.name
    schema_module.close_stream_arena(owner)
    assert schema_module.stream_arena(0x7A11) is None and owner.closed and not owner.holds((1, 0, 0, 0, 1, 1))
    with pytest.raises(GeometryArenaError):
        GeometryArenaWriter(name, families=FAMILIES)


def test_control_a_retired_family_kept_live_is_seen(arena):
    sticky = _mutated(arena_module, ("        self._named = named\n", "        self._named = {**self._named, **named}\n"))
    with pytest.raises(AssertionError):
        _check_retirement(arena, sticky)


def _check_resize(arena, module):
    owner, attach = arena
    writer = attach(module)
    small = _family(51, capacity=2)
    grown = replace(small, capacity=3, geometry=bytes(CHAIN_GEOMETRY_BYTES * 3))
    projector = DriftRecordProjector(writer.namespace, 2, 3)
    fields = []
    for sequence, descriptor in enumerate((small, grown), 1):
        state = _state(descriptor)
        _publish(writer, state, 0, sequence)
        fields.append(projector.project(state.mode_state, held=owner.holds)[0])
    # The same revision at another capacity: a new key in the other bank, the epoch kept, the old key still whole.
    assert _bank_keys(owner) == [(51, 2), (51, 3)]
    assert fields[0]["chains_geometry_key"] != fields[1]["chains_geometry_key"]
    assert fields[0]["chains_epoch"] == fields[1]["chains_epoch"]
    assert owner.holds(writer.key_for("chains", small, 2, 3)) and owner.holds(writer.key_for("chains", grown, 2, 3))


def test_a_resize_is_a_new_key_beside_the_old_one_in_the_same_epoch(arena):
    _check_resize(arena, arena_module)


def test_control_a_key_without_its_capacity_is_seen(arena):
    blind = _mutated(arena_module, ("int(descriptor.revision), int(descriptor.capacity))",
                                    "int(descriptor.revision), 2)"))
    with pytest.raises(AssertionError):
        _check_resize(arena, blind)


def _check_replacement(arena, module):
    owner, attach = arena
    first = attach(module)
    descriptor = _family(61)
    _publish(first, _state(descriptor), 0, 1)
    old = first.key_for("chains", descriptor, 2, 3)
    first.close()
    second = attach(module)
    new = second.key_for("chains", descriptor, 2, 3)
    # A replacement worker is another namespace: the dead writer's bank is never the new key.
    assert owner.writer_namespace() == second.namespace != first.namespace
    assert old != new and owner.holds(old) and not owner.holds(new)
    _publish(second, _state(descriptor), 0, 1)
    assert owner.holds(new)


def test_a_replacement_writer_keys_its_geometry_in_another_namespace(arena):
    _check_replacement(arena, arena_module)


def test_control_a_replacement_writer_reusing_a_namespace_is_seen(arena):
    fixed = _mutated(arena_module, ("self.namespace = secrets.randbits(63) | 1", "self.namespace = 1"))
    with pytest.raises(AssertionError):
        _check_replacement(arena, fixed)


_CPP_FIELDS = re.compile(r"held\.(\w+) = (u32|u64)At\(header \+ (\d+)\);")


def _cpp_bank_reader(source):
    """The C++ reader's bank-header fields (geometry_arena.cpp's read) as (name, struct format, offset)."""
    fields = [(name, "<I" if kind == "u32" else "<Q", int(at)) for name, kind, at in _CPP_FIELDS.findall(source)]
    assert {name for name, _, _ in fields} == {"ns", "engine", "activation", "family", "capacity", "revision"}
    return fields


def _check_cpp_layout(arena, source):
    owner, attach = arena
    writer = attach()
    geometry = (bytes(range(256)) * 64)[:CHAIN_GEOMETRY_BYTES * 3]
    descriptor = replace(_family(0x1_0000_0071, capacity=3), geometry=geometry)
    _publish(writer, _state(descriptor, engine=9, activation=4), 0, 1)
    at = bank_offset(CHAINS, 0, owner.bank_bytes)
    view = owner._memory.buf
    read = {name: struct.unpack_from(fmt, view, at + offset)[0] for name, fmt, offset in _cpp_bank_reader(source)}
    assert read == {"ns": writer.namespace, "engine": 9, "activation": 4, "family": CHAINS, "capacity": 3,
                    "revision": 0x1_0000_0071}
    assert struct.unpack_from("<I", view, at + 4)[0] == len(geometry)  # the payload bytes the reader copies
    assert bytes(view[at + BANK_HEADER_BYTES:at + BANK_HEADER_BYTES + len(geometry)]) == geometry
    # The arena header the reader validates (magic, version, families, banks, bank bytes, header sizes).
    assert struct.unpack_from("<IIIIQII", view, 0) == (0x41475253, 1, len(FAMILIES), 2, owner.bank_bytes, 64, 64)


def test_the_writer_packs_the_bank_header_the_cpp_reader_reads(arena):
    source = (ROOT / "native/core/src/geometry_arena.cpp").read_text(encoding="utf-8")
    _check_cpp_layout(arena, source)
    swapped = source.replace("u32At(header + 28)", "u32At(header + 20)")
    with pytest.raises(AssertionError):
        _check_cpp_layout(arena, swapped)


class _Item:
    def __init__(self):
        self.names = []

    def geometry_arena(self, name):
        self.names.append(name)


def _check_route_names_arena(module):
    owner = module.open_stream_arena(0x5EED, CHAIN_GEOMETRY_BYTES * 4)
    writer = GeometryArenaWriter(owner.name, families=FAMILIES)
    try:
        route, item = module.DriftStream(), _Item()
        route.bound(item, {"runtime_generation": 7, "engine_generation": 2, "activation_id": 3, "mode_code": 9})
        descriptor = _family((0x5EED << 32) + 1)
        for sequence in (1, 2, 3):
            state = _state(descriptor, serials=(sequence,))
            _publish(writer, state, 0, sequence)
            logical = SimpleNamespace(runtime_generation=7, **vars(state))
            fields = route.project(logical)
            assert owner.holds(arena_module.key_of_words(fields["chains_geometry_key"]))
        # Unbound at bind (""), then the stream's arena once; the identity is the writer's namespace and the frame's.
        assert item.names == ["", owner.name]
        assert arena_module.key_of_words(fields["chains_geometry_key"])[:3] == (writer.namespace, 2, 3)
        other = _Item()
        route.bound(other, {"runtime_generation": 8, "engine_generation": 2, "activation_id": 3, "mode_code": 9})
        route.project(SimpleNamespace(runtime_generation=7, **vars(_state(descriptor, serials=(4,)))))
        assert other.names == [""]                    # another stream's item is never told this arena
    finally:
        writer.close()
        module.close_stream_arena(owner)


def test_the_route_names_the_stream_arena_to_its_bound_item_once():
    _check_route_names_arena(schema_module)


def test_control_a_route_naming_the_arena_every_record_is_seen():
    chatty = _mutated(schema_module, ("if item is not None and bound == identity and told[0] != name:",
                                      "if item is not None and bound == identity:"))
    with pytest.raises(AssertionError):
        _check_route_names_arena(chatty)


def _check_unactivated(arena, module):
    owner, attach = arena
    writer = attach(module)
    _publish(writer, _state(_family(81), activation=-1), 0, 1)
    assert writer.writes == 0 and _bank_keys(owner) == [(0, 0), (0, 0)]
    route_fields = schema_module.DriftStream().project(
        SimpleNamespace(runtime_generation=1, **vars(_state(_family(81), activation=-1))))
    assert route_fields["chains_geometry_key"] == (0,) * 8


def _check_real_link_owns_the_arena(initial_mode):
    """A real owner, link and (in-process) worker session: the main process owns the arena from a configure with a
    live drift family, or stages it at the hidden activation into one; the worker writes it under its namespace; the
    arena retires with the link."""
    from tests.test_visualizer_engine_frame_capacity import _settings
    from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor, _pump
    from tools.visualizer_replay import owner_worker_gate as gate
    from tools.visualizer_replay.live_engine_gate import paced_pcm
    from core.settings.visualizer_presets import get_custom_preset_index
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer.feature_replay import offline_activation_request

    supervisor, clock = _InProcessSupervisor(), [0.]
    rig = gate.OwnerRig(initial_mode, worker=True, supervisor=supervisor, cadence='thread', clock=clock,
                        extra_modes=('extruded_bubble',))
    settings = _settings('extruded_bubble', True)
    if initial_mode == 'extruded_bubble':
        rig.widgets['spotify_visualizer'].update({k: v for k, v in settings.items() if k.startswith('extruded_bubble_')})
        rig.widgets['spotify_visualizer'].update(preset_extruded_bubble=get_custom_preset_index(initial_mode))
    try:
        pcm, rate = paced_pcm(.5)
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm, pcm_rate=rate):
            owner = rig.build()
        link = owner._worker
        if initial_mode != 'extruded_bubble':
            assert link._geometry_arena is None
            assert owner.request_mode_change('extruded_bubble',
                                             **offline_activation_request('extruded_bubble', 0, None, settings))
            for step in range(100):
                clock[0] = .05 * (step + 1)
                _pump(rig, .01)
                if owner.controller.mode_id == 'extruded_bubble' and owner._worker_commit is None:
                    break
        arena = link._geometry_arena
        assert arena is not None and schema_module.stream_arena(link.label_namespace) is arena
        session_writer = supervisor.worker._session._geometry_writer
        assert session_writer.name == arena.name and arena.writer_namespace() == session_writer.namespace
        for step in range(100):
            clock[0] += .05
            _pump(rig, .01)
            if session_writer.writes:
                break
        assert session_writer.writes and any(arena.holds(key) for key in session_writer._named.values())
    finally:
        rig.close()
        supervisor.close()
        engine_worker_link.reset_run_state_for_testing()
    assert arena.closed and schema_module.stream_arena(link.label_namespace) is None


@pytest.mark.qt
@pytest.mark.parametrize('initial_mode', ('extruded_bubble', 'spectrum'), ids=('configure', 'mode_change'))
def test_the_real_link_owns_the_arena_and_the_worker_writes_it(qt_app, initial_mode):
    _check_real_link_owns_the_arena(initial_mode)


@pytest.mark.qt
def test_a_link_closed_before_the_activation_reply_closes_its_staged_arena(qt_app, monkeypatch):
    """A mode change stages an arena and the link closes while its reply is pending (the reply is abandoned, neither
    ``committed`` nor ``failed`` runs): the staged arena is closed and unlinked with the link, never leaked."""
    from tests.test_visualizer_engine_frame_capacity import _settings
    from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor
    from tools.visualizer_replay import owner_worker_gate as gate
    from tools.visualizer_replay.live_engine_gate import paced_pcm
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer.feature_replay import offline_activation_request

    staged, stage = [], schema_module.stage_stream_arena
    monkeypatch.setattr(schema_module, 'stage_stream_arena', lambda n: staged.append(stage(n)) or staged[-1])
    supervisor, clock = _InProcessSupervisor(), [0.]
    rig = gate.OwnerRig('spectrum', worker=True, supervisor=supervisor, cadence='thread', clock=clock,
                        extra_modes=('extruded_bubble',))
    try:
        pcm, rate = paced_pcm(.5)
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm, pcm_rate=rate):
            owner = rig.build()
        link = owner._worker
        replies = []
        activation = offline_activation_request('extruded_bubble', 0, None, _settings('extruded_bubble', True))
        link.set_mode('extruded_bubble', activation, on_committed=lambda *a: replies.append(a),
                      on_failed=replies.append)
        assert len(staged) == 1 and not staged[0].closed
        link.close()
        assert not replies and staged[0].closed
    finally:
        rig.close()
        supervisor.close()
        engine_worker_link.reset_run_state_for_testing()


@pytest.mark.qt
def test_control_an_activation_without_its_arena_is_seen(qt_app, monkeypatch):
    import core.visualizer_engine.frame_capacity as frame_capacity
    monkeypatch.setattr(frame_capacity, 'geometry_bank_bytes', lambda mode, kwargs: 0)
    with pytest.raises(AssertionError):
        _check_real_link_owns_the_arena('spectrum')


def test_an_unactivated_frame_writes_and_names_no_key(arena):
    _check_unactivated(arena, arena_module)


def test_control_an_unactivated_frame_reaching_the_bank_is_seen(arena):
    unguarded = _mutated(arena_module, ("        if not (0 <= engine <= _U32_MAX and 0 <= activation <= _U32_MAX):\n"
                                        "            self._pending = None",
                                        "        if False:\n            self._pending = None"))
    with pytest.raises((AssertionError, struct.error)):
        _check_unactivated(arena, unguarded)


# ----------------------------------------------------------------------------------- sub-box 2: the compute stream

def _upload_reference():
    from rendering.quick.visualizer.implementations.extruded_bubble_drift_solver import _upload
    return _upload


def _records(frame):
    return np.frombuffer(frame.drift_steps, dtype="<f8").reshape(-1, STEP_FLOATS)


def _cursor(serials, count, last_applied):
    """(the step a record's solver begins at, whether it begins fresh): the first step past the last one applied (the
    serials are increasing but need not be consecutive), fresh when that step does not follow it (a gap, or a window
    that begins after it: the whole window restarts), as ``DriftSteps.after`` plans the Python solver's work."""
    window = list(serials[:count])
    first = sum(1 for serial in window if serial <= last_applied)
    return first, first < count and window[first] != last_applied + 1


def _suffix(stream, count, first):
    """The steps ``first:`` of a packed stream with their knot starts made relative to step ``first``, then their knots
    (what the cursor hands the solver)."""
    steps = np.frombuffer(stream[:count * STEP_FLOATS * 4], dtype="<f4").reshape(count, STEP_FLOATS).copy()
    knots = stream[count * STEP_FLOATS * 4:]
    base = int(steps[first, STEP_INDEX["serial"]]) if first < count else int(len(knots) // KNOT_DECISION_BYTES)
    steps = steps[first:]
    steps[:, STEP_INDEX["serial"]] -= base
    return steps.tobytes() + knots[base * KNOT_DECISION_BYTES:]


def _check_stream(pack, cursor):
    upload = _upload_reference()
    serials, counts = (3, 4, 6, 7, 9), (2, 0, 3, 1, 4)        # a tick without a live family records no step
    frame = _frame(serials, _family(91, first=3), knot_counts=counts, seed=4)
    records, starts = _records(frame), knot_starts(_records(frame))
    stream = pack(DriftSteps(frame.drift_steps, frame.drift_knots, 3, 9))
    count, ordered = schema_module.drift_step_serials(DriftSteps(frame.drift_steps, frame.drift_knots, 3, 9))
    assert count == 5 and ordered[:5] == serials and not any(ordered[5:])
    # The whole window is the Python solver's restart upload.
    assert stream == upload(records, starts, frame.drift_knots, 0, 5)
    for last_applied in (6, 7, 3, 9, 1, 2, 4, 5):
        first, restart = cursor(ordered, count, last_applied)
        suffix, fresh = DriftSteps(frame.drift_steps, frame.drift_knots, 3, 9).after(last_applied)
        assert restart == fresh
        # The cursor's suffix is the solver's own upload of the steps after the last applied one (a short gap), the
        # whole window after a restart, and nothing for a repeated record.
        assert _suffix(stream, count, first) == upload(records, starts, frame.drift_knots, first, 5)
        assert len(suffix.steps) // (STEP_FLOATS * 8) == 5 - first


def test_the_drift_stream_is_the_solvers_upload_and_the_cursor_its_suffix():
    _check_stream(schema_module.pack_drift_stream, _cursor)


def test_control_a_stream_keeping_the_serial_slot_is_seen():
    raw = _mutated(schema_module, ("    gpu[:, _KNOT_START] = starts[:-1]\n", ""))
    with pytest.raises(AssertionError):
        _check_stream(raw.pack_drift_stream, _cursor)


def test_control_a_cursor_assuming_consecutive_serials_is_seen():
    def consecutive(serials, count, last_applied):
        first = last_applied - serials[0] + 1
        return (first, False) if 0 <= first <= count else (0, True)
    with pytest.raises(AssertionError):
        _check_stream(schema_module.pack_drift_stream, consecutive)


def _check_repeated(module):
    descriptor = _family(101, first=1)
    frame = _frame((1, 2, 3), descriptor, knot_counts=(1, 2, 3), seed=5)
    projector = module.DriftRecordProjector(5, 2, 3)
    a, _ = projector.project(frame)
    b, _ = projector.project(frame)
    # A record the core sees again changes no trigger (drift_last_step) and no stream: the entry is not due, and a
    # record the core missed still carries the whole window its cursor needs.
    assert a == b and a["drift_last_step"] == 3 and a["drift_stream_used"] * 4 == len(a["drift_stream"]) > 0
    empty, _ = module.DriftRecordProjector(5, 2, 3).project(ExtrudedBubbleFrame())
    assert empty["drift_stream"] == b"" and empty["drift_stream_used"] == empty["drift_step_count"] == 0


def test_a_repeated_record_carries_the_same_stream_and_trigger():
    _check_repeated(schema_module)


def test_control_a_stream_of_only_the_steps_since_the_last_record_is_seen():
    since = _mutated(schema_module, ("        stream = pack_drift_stream(window)\n",
                                     "        stream = pack_drift_stream(window.after(self._last_serial)[0])\n"))
    with pytest.raises(AssertionError):
        _check_repeated(since)


def _check_full_window(rows):
    serials = tuple(range(1, STEP_HISTORY + 1))
    frame = _frame(serials, _family(111, first=1), knot_counts=(rows,) * STEP_HISTORY, seed=6)
    fields, _ = DriftRecordProjector(5, 2, 3).project(frame)
    layout = NativeLayout.build(DRIFT_RECORD_ENTRIES)
    assert layout.size <= MAX_RECORD_BYTES
    payload = layout.pack(native_schema_id(MODE_CODES["extruded_bubble"], 1), fields)
    at = layout.field("drift_stream").offset
    assert layout.unpack(payload)["drift_stream_used"] == DRIFT_STREAM_FLOATS
    assert payload[at:at + DRIFT_STREAM_FLOATS * 4] == fields["drift_stream"]       # carried verbatim


def test_a_full_window_at_every_drawable_chain_fits_the_record():
    _check_full_window(CHAIN_PATHS)
    with pytest.raises(NativeSchemaError):
        _check_full_window(CHAIN_PATHS + 1)
