"""N3.2 (decision D15; ``native/core/src/mesh_buffers.h``): the GPU-free parts of meshes and buffers.

- the block arena's layout (``rendering.native.streams.arena_layout``, the core's ``arenaLayout`` mirrored);
- the record's ``f32`` field kind (a stream's bytes verbatim) in the Python reference;
- a program's packs in order (a geometry pass's fragment, vertex and draw-parameters packs) and its declaration;
- the core's sources hold the contract's names (the per-batch core member, the module entries, ABI 18).
"""
from __future__ import annotations

import json
import re
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native" / "core" / "src"


# --------------------------------------------------------------------------------------------- the arena

def _overlaps(offsets, sizes):
    spans = sorted(zip(offsets, sizes))
    return any(a + s > b for (a, s), (b, _t) in zip(spans, spans[1:]))


@pytest.mark.parametrize("alignment", [1, 16, 64, 256])
def test_the_arena_places_every_block_aligned_and_apart(alignment):
    from rendering.native.streams import arena_layout

    sizes = [16, 64, 16, 336, 336, 336, 16, 0, 1040]
    offsets, size = arena_layout(sizes, alignment)
    assert len(offsets) == len(sizes)
    assert all(o % alignment == 0 for o in offsets)
    assert not _overlaps(offsets, sizes)
    assert size % alignment == 0 and size >= offsets[-1] + sizes[-1]
    # Equal blocks in a row (a batched pass's copies) sit one aligned stride apart.
    stride = offsets[4] - offsets[3]
    assert stride == offsets[5] - offsets[4] and stride % alignment == 0 and stride >= 336


def test_the_arena_check_sees_a_layout_that_ignores_the_alignment():
    """Negative control: blocks packed back to back (no alignment) fail the alignment check above at 256."""
    sizes = [16, 64, 336]
    naive = [0, 16, 80]
    assert not all(o % 256 == 0 for o in naive)
    assert not _overlaps(naive, sizes)          # it is the alignment the check catches, not an overlap


def test_the_core_arena_rule_is_the_mirror_s(tmp_path):
    """The core's arenaLayout is the same arithmetic (read from its source: round each offset up, the size up)."""
    text = (CORE / "mesh_buffers.cpp").read_text(encoding="utf-8")
    body = text[text.index("ArenaLayout arenaLayout("):]
    body = body[:body.index("\n}\n")]
    assert "offset = (offset + align - 1) / align * align;" in body
    assert "layout.size = (offset + align - 1) / align * align;" in body


# --------------------------------------------------------------------------------------------- the f32 kind

def test_an_f32_stream_field_carries_its_bytes_verbatim():
    from core.visualizer_engine.native_schema import NativeLayout

    layout = NativeLayout.build((("points", "f32", 12), ("points_len", "u32", 1)))
    field = layout.field("points")
    assert field.offset % 16 == 0 and field.size == 48
    payload = struct.pack("<6f", 0.5, -1.25, 3.0, 1e-3, 7.0, 2.5)
    record = layout.pack(0x10109, {"points": payload, "points_len": 6})
    assert record[field.offset:field.offset + len(payload)] == payload
    assert record[field.offset + len(payload):field.offset + field.size] == bytes(field.size - len(payload))
    assert layout.unpack(record)["points"][:6] == struct.unpack("<6f", payload)


def test_an_f32_field_past_its_capacity_is_refused():
    from core.visualizer_engine.native_schema import MAX_STREAM_FIELD_COUNT, NativeLayout, NativeSchemaError

    layout = NativeLayout.build((("points", "f32", 4),))
    with pytest.raises(NativeSchemaError):
        layout.pack(0x10109, {"points": bytes(20)})
    with pytest.raises(ValueError):
        NativeLayout.build((("points", "f32", MAX_STREAM_FIELD_COUNT + 1),))
    with pytest.raises(ValueError):
        NativeLayout.build((("bars", "f64", 4097),))     # the other kinds keep their 4096


def test_the_generated_header_and_the_runtime_reader_know_the_f32_kind():
    header = (CORE / "frame_abi_generated.h").read_text(encoding="utf-8")
    assert "enum class FieldKind : quint8 { U32, F64, F64x4, F32 };" in header
    schema = (CORE / "mode_schema.cpp").read_text(encoding="utf-8")
    assert 'kind == QLatin1String("f32")' in schema and "kMaxStreamCount = 262144" in schema
    from core.visualizer_engine import native_schema

    assert native_schema.MAX_STREAM_FIELD_COUNT == 262144 and native_schema.MAX_RECORD_BYTES == 1 << 21
    assert "constexpr quint32 kMaxRecordBytes = 1u << 21;" in schema


# --------------------------------------------------------------------------------------------- the program

def _geometry_pass(name, *, batched=False, dp=b""):
    from rendering.native.mode import ModePass, PassGeometry

    geometry = PassGeometry(b"V-" + name.encode(), topology="triangle_strip", vertices=4, instances="count",
                            storage=(("Records", "records"),),
                            batches="batch_table" if batched else None, batch_count="batch_len" if batched else None,
                            draw_parameters_pack=dp)
    return ModePass(name, b"F-" + name.encode(), "additive", geometry=geometry)


def test_a_geometry_pass_takes_its_vertex_pack_after_its_fragment_pack():
    from rendering.native.mode import CapturePass, ModePass, ModeStream, program_json

    plain = ModePass("plain", b"F-plain", "alpha")
    declared, packs = program_json(
        (plain, _geometry_pass("sprites"), CapturePass("grab", "scene"), _geometry_pass("batched", batched=True,
                                                                                         dp=b"D-batched")),
        streams=(ModeStream("records", "record_rows"),))
    assert packs == [b"F-plain", b"F-sprites", b"V-sprites", b"", b"F-batched", b"V-batched", b"D-batched"]
    program = json.loads(declared)
    assert [s["name"] for s in program["streams"]] == ["records"]
    sprites = program["passes"][1]
    assert sprites["vertex"] is True and sprites["topology"] == "triangle_strip"
    assert sprites["storage"] == [{"name": "Records", "stream": "records"}]
    assert "vertex" not in program["passes"][0]          # a pass on the core's triangle declares as N3.1's did


def test_a_batched_pass_without_a_draw_parameters_pack_still_takes_its_slot():
    from rendering.native.mode import program_json

    _declared, packs = program_json((_geometry_pass("batched", batched=True),))
    assert packs == [b"F-batched", b"V-batched", b""]


def test_the_python_face_refuses_what_the_core_refuses():
    from rendering.native.mode import BlendState, ModeStream, PassGeometry, RecordLayout, MeshAttribute

    with pytest.raises(ValueError):
        PassGeometry(b"v", topology="points")
    with pytest.raises(ValueError):
        PassGeometry(b"v", indirect="commands")             # no draw_count
    with pytest.raises(ValueError):
        PassGeometry(b"v", draw_parameters_pack=b"d")       # not batched
    with pytest.raises(ValueError):
        ModeStream("s", "f", "instance")                    # an instance stream has a layout
    with pytest.raises(ValueError):
        RecordLayout(8, (MeshAttribute("aPoint", 4, 0),))   # past its record
    with pytest.raises(ValueError):
        BlendState(("max", "one", "one"), ("max", "one", "two"))
    assert BlendState(("max", "one", "one"), ("max", "one", "one")).declaration() == {
        "color": ["max", "one", "one"], "alpha": ["max", "one", "one"]}


# --------------------------------------------------------------------------------------------- the sources

def test_the_python_core_members_hold_the_per_batch_member():
    from rendering.native.mode import MODE_CORE_MEMBERS

    source = (CORE / "mode_content.cpp").read_text(encoding="utf-8")
    rows = dict(re.findall(r'\{ "(\w+)", (\d+), (?:true|false), \w+ \},', source))
    assert "u_srpss_batch" in rows and MODE_CORE_MEMBERS["u_srpss_batch"][0] == int(rows["u_srpss_batch"])
    assert (CORE / "mesh_buffers.cpp").read_text(encoding="utf-8").count('kBatchMember[] = "u_srpss_batch"') == 1


def test_the_module_declares_n3_2_s_entries_at_abi_18():
    module = (CORE / "module.cpp").read_text(encoding="utf-8")
    for entry in ("composite_mode_mesh", "composite_mode_mesh_remove", "mesh_buffer_control",
                  "mesh_buffer_arena_layout", "vulkan_device_facts"):
        assert f'{{ "{entry}", {entry}, METH_VARARGS,' in module, entry
    assert "#define SRPSS_NATIVE_CORE_ABI 18" in (CORE / "abi.h").read_text(encoding="utf-8")
    from rendering.native.loader import EXPECTED_ABI

    assert EXPECTED_ABI == 18
