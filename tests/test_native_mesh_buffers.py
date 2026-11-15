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


# --------------------------------------------------------------------------------------------- on the built module
# GPU-free, on release/native_module (compiled only on GitHub; these skip without it).

import os
import sys

from rendering.native import loader

MODULE_DIR = ROOT / "release" / "native_module"
BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()
HARNESS = ROOT / "native" / "core" / "python"
built = pytest.mark.skipif(
    not BUILT, reason=f"the native core is not built in this checkout: no release/native_module/{loader.MODULE_NAME}.pyd")


@pytest.fixture(scope="module")
def core():
    from rendering import native

    loaded = native.load(MODULE_DIR)
    if loaded.abi < 18:
        pytest.skip(f"the built module speaks ABI {loaded.abi}; meshes and buffers are ABI 18")
    return loaded


@pytest.fixture(scope="module")
def mb_packs(tmp_path_factory):
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    import mesh_buffers
    import probe_rings

    folder = tmp_path_factory.mktemp("mesh_buffers")
    return {name: probe_rings.bake(mesh_buffers.compose(mesh_buffers.SHADERS[name]), name, folder)
            for name in ("streak.vert", "streak.frag", "beam.vert", "beam.frag", "cell.vert", "cell.frag")}


def _mb():
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    import mesh_buffers

    return mesh_buffers


def _item_clip(card, target):
    """itemClipMatrix's arithmetic (mode_content.cpp), uncorrected, as rows: item pixels to the target's clip space."""
    ox, oy = card["oriented_size"]
    r, t = [1, 0, 0, 1], [0, 0]
    quarters = card["quarters"] & 3
    if quarters == 1:
        r, t = [0, 1, -1, 0], [0, oy]
    elif quarters == 2:
        r, t = [-1, 0, 0, -1], [ox, oy]
    elif quarters == 3:
        r, t = [0, -1, 1, 0], [ox, 0]
    w, m = card["window_from_target"], card["item_from_window"]
    a = [m[0] * w[0] + m[1] * w[3], m[0] * w[1] + m[1] * w[4], m[0] * w[2] + m[1] * w[5] + m[2],
         m[3] * w[0] + m[4] * w[3], m[3] * w[1] + m[4] * w[4], m[3] * w[2] + m[4] * w[5] + m[5]]
    det = a[0] * a[4] - a[1] * a[3]
    inv = [a[4] / det, -a[1] / det, 0.0, -a[3] / det, a[0] / det, 0.0]
    inv[2] = -(inv[0] * a[2] + inv[1] * a[5])
    inv[5] = -(inv[3] * a[2] + inv[4] * a[5])
    px = [inv[0] * r[0] + inv[1] * r[2], inv[0] * r[1] + inv[1] * r[3], inv[0] * t[0] + inv[1] * t[1] + inv[2]]
    py = [inv[3] * r[0] + inv[4] * r[2], inv[3] * r[1] + inv[4] * r[3], inv[3] * t[0] + inv[4] * t[1] + inv[5]]
    width, height = target
    return [[2 / width * px[0], 2 / width * px[1], 0, 2 / width * px[2] - 1],
            [-2 / height * py[0], -2 / height * py[1], 0, 1 - 2 / height * py[2]],
            [0, 0, 1, 0], [0, 0, 0, 1]]


def _rows(column_major):
    return [[column_major[c * 4 + r] for c in range(4)] for r in range(4)]


def _times(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def _apply(rows, x, y):
    return [sum(rows[r][c] * v for c, v in enumerate((x, y, 0.0, 1.0))) for r in range(4)]


# Each backend's correction as conventions.cpp's targetCorrection makes it: QRhi's clipSpaceCorrMatrix times the
# core's own Y flip where the framebuffer is Y-up (OpenGL). Column-major.
CORRECTIONS = {
    "none": None,
    "opengl": [1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],            # identity * flip(1, -1, 1)
    "vulkan": [1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 0.5, 0, 0, 0, 0.5, 1],        # QRhi's Vulkan clipSpaceCorrMatrix
}


def _streak_blocks(core, mb_packs, card, target, correction):
    from rendering.native.mode import ModePass, PassGeometry, mode_blocks

    mb = _mb()
    geometry = PassGeometry(mb_packs["streak.vert"], topology="triangle_strip", mesh="quad", vertices="mesh",
                            instances=4)
    passes = (ModePass("streaks", mb_packs["streak.frag"], "additive", geometry=geometry),)
    schema = mb.schema("streaks", (("u_frame", "f64", 1),))
    record = schema.encode({"u_frame": 0.0})
    blocks, facts = mode_blocks(core.module, schema, passes, {"u_spread": [6.0, 36.0], "u_colour": [1, 1, 1, 1]},
                                record, card, target, correction=correction)
    layout, _facts = core.program_block_pack(mb_packs["streak.vert"], "StreakDraw", {})
    offset = next(m[2] for m in _facts["layout"]["members"] if m[0] == "uMatrix")
    return list(struct.unpack_from("<16f", blocks[0], offset))


@built
@pytest.mark.parametrize("backend", sorted(CORRECTIONS))
def test_umatrix_is_item_pixels_to_the_targets_clip_space_corrected_once(core, mb_packs, backend):
    """D15 choice H: a pass with its own vertex stage gets uMatrix = correction * itemClip (column-major), the item's
    unrotated pixels (y down) to the drawn target's clip space; on the harness card the item's corners land on the
    clip square's corners (y up before the correction), and each backend's correction is applied exactly once."""
    import probe_rings

    card = probe_rings.harness_card((480, 270), 1.5)
    target = (720, 405)
    got = _rows(_streak_blocks(core, mb_packs, card, target, CORRECTIONS[backend]))
    expected = _item_clip(card, target)
    if CORRECTIONS[backend] is not None:
        expected = _times(_rows(CORRECTIONS[backend]), expected)
    assert all(abs(got[r][c] - expected[r][c]) < 1e-6 for r in range(4) for c in range(4)), (got, expected)
    top_left, bottom_right = _apply(got, 0.0, 0.0), _apply(got, 480.0, 270.0)
    flip = -1.0 if backend != "none" else 1.0              # both of the core's backends flip Y once
    assert abs(top_left[0] + 1) < 1e-6 and abs(top_left[1] - flip) < 1e-6
    assert abs(bottom_right[0] - 1) < 1e-6 and abs(bottom_right[1] + flip) < 1e-6


@built
def test_umatrix_follows_the_cards_rotation_and_window_map(core, mb_packs):
    """A rotated card (a quarter turn) at an odd window offset: the item's rotation and the target's map are in uMatrix
    (against itemClipMatrix's arithmetic); negative control: the upright card's matrix differs."""
    import probe_rings

    card = dict(probe_rings.harness_card((480, 270), 1.5), quarters=1, oriented_size=[270.0, 480.0],
                window_from_target=[1.0, 0.0, 3.0, 0.0, 1.0, 5.0])
    target = (405, 720)
    got = _rows(_streak_blocks(core, mb_packs, card, target, None))
    expected = _item_clip(card, target)
    assert all(abs(got[r][c] - expected[r][c]) < 1e-5 for r in range(4) for c in range(4)), (got, expected)
    upright = _item_clip(dict(card, quarters=0), target)
    assert any(abs(got[r][c] - upright[r][c]) > 1e-3 for r in range(4) for c in range(4))


def _beam(core, mb_packs, entries, checks, stream):
    from rendering.native.mode import ModePass, PassGeometry, mode_blocks

    import probe_rings

    mb = _mb()
    geometry = PassGeometry(mb_packs["beam.vert"], topology="triangle_strip", vertices=4, instances="segments",
                            storage=(("Trace", "trace"),))
    passes = (ModePass("beam", mb_packs["beam.frag"], "additive", geometry=geometry),)
    schema = mb.schema("beam", tuple(entries), tuple(checks))
    values = {name: (bytes(4 * count) if kind == "f32" else (0.0 if kind == "f64" else
                     (0 if count == 1 else (0,) * count))) for name, kind, count in entries}
    return mode_blocks(core.module, schema, passes, {"u_beam": [2.5, 1.5, 0, 0], "u_colour": [1, 1, 1, 1]},
                       schema.encode(values), probe_rings.harness_card((480, 270), 1.0), (480, 270),
                       streams=(stream,))


BEAM = [("trace_rows", "f32", 512), ("segments", "u32", 1), ("trace_floats", "u32", 1)]
BEAM_CHECKS = [("segments", "at_most", 255), ("trace_floats", "at_most", 512)]


@built
def test_an_f32_stream_is_admitted_with_its_used_length(core, mb_packs):
    from rendering.native.mode import ModeStream

    blocks, facts = _beam(core, mb_packs, BEAM, BEAM_CHECKS, ModeStream("trace", "trace_rows", used="trace_floats"))
    streams = facts["program"]["streams"]
    assert streams[0]["used"] == "trace_floats" and streams[0]["field"] == "trace_rows"


@built
@pytest.mark.parametrize("case, entries, checks, used, reason", [
    ("no used length", BEAM, BEAM_CHECKS, None, "names its used length"),
    ("no at_most rule", BEAM, BEAM_CHECKS[:1], "trace_floats", "takes an at_most rule"),
    ("a rule past the capacity", BEAM, [BEAM_CHECKS[0], ("trace_floats", "at_most", 513)], "trace_floats",
     "takes an at_most rule"),
    ("not a u32 scalar", BEAM[:2] + [("trace_floats", "f64", 1)], BEAM_CHECKS[:1], "trace_floats", "a u32 scalar"),
    ("no such field", BEAM[:2], BEAM_CHECKS[:1], "trace_floats", "no used-length field"),
    ("a u32 stream", [("trace_rows", "u32", 512)] + BEAM[1:], BEAM_CHECKS, "trace_floats",
     "belongs to an f32 field"),
])
def test_the_used_length_is_refused_with_its_reason(core, mb_packs, case, entries, checks, used, reason):
    """D15 point 4 (the lead, 15 Nov): an f32 stream writes only its used elements, so the core admits it only with a
    u32 used-length field whose at_most rule keeps it within the field."""
    from rendering.native.mode import ModeStream

    with pytest.raises(ValueError, match=reason):
        _beam(core, mb_packs, entries, checks, ModeStream("trace", "trace_rows", used=used))


@built
def test_the_used_length_is_the_streams_alone(core, mb_packs):
    """One owner a name: the used length is the stream's and may not also be a draw count."""
    from rendering.native.mode import ModeStream

    with pytest.raises(ValueError, match="two of"):
        _beam(core, mb_packs, BEAM[:2], [("segments", "at_most", 255)],
              ModeStream("trace", "trace_rows", used="segments"))


def _cells(core, mb_packs, pairs):
    """The harness's batched cells pass over a batch table of ``pairs`` {first, count} pairs, through mode_blocks."""
    from rendering.native.mode import ModePass, ModeStream, PassGeometry, mode_blocks

    import probe_rings

    mb = _mb()
    geometry = PassGeometry(mb_packs["cell.vert"], topology="triangle_strip", vertices=4,
                            storage=(("Cells", "cells"), ("Batches", "batches")), batches="batch_table",
                            batch_count="batch_len")
    passes = (ModePass("cells", mb_packs["cell.frag"], "alpha", geometry=geometry),)
    entries = (("cell_rows", "f32", 4 * mb.CELLS), ("batch_table", "u32", 2 * pairs), ("cell_floats", "u32", 1),
               ("batch_len", "u32", 1))
    schema = mb.schema("cells", entries, (("cell_floats", "at_most", 4 * mb.CELLS), ("batch_len", "at_most", pairs)))
    record = schema.encode({"cell_rows": bytes(16 * mb.CELLS), "batch_table": (0,) * (2 * pairs), "cell_floats": 0,
                            "batch_len": 0})
    return mode_blocks(core.module, schema, passes, {"u_tint": [1.0, 1.0, 1.0, 1.0]}, record,
                       probe_rings.harness_card((480, 270), 1.0), (480, 270),
                       streams=(ModeStream("cells", "cell_rows", used="cell_floats"),
                                ModeStream("batches", "batch_table")))


@built
def test_a_batch_table_past_the_batch_cap_is_refused(core, mb_packs):
    """Checkpoint audit 4, L4: D15 point 6's cap of 64 batches a pass is an admission refusal (the arena's copies and
    the batched commands hold 64), never a silent cap that leaves the batches past it undrawn. Control: 64 pairs are
    admitted (on the e95d9306 module, 65 were admitted too: the test failed there)."""
    _cells(core, mb_packs, 64)
    with pytest.raises(ValueError, match="1 to 64"):
        _cells(core, mb_packs, 65)
