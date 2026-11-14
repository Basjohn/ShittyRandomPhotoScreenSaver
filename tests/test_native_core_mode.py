"""N2.9's generic mode content and the audit's program-block edges (14 Nov, L2) on the built module, GPU-free.

The module is compiled only on GitHub; without ``release/native_module`` these tests skip and say so. The drawn proof
is ``native/core/python/generic_mode_check.py`` (its ``blocks`` round holds the full refusal table).

- ``mode_blocks``: Probe Rings' record and settings packed by name into each pass's blocks; a record field no pass
  declares, a setting left out, a value without a defined conversion (NaN, an int beyond int32) are refused.
- ``program_block_pack`` (L2): a mat3 and a multi-dimensional array are never packed and always listed unfilled (setting
  one is refused); an int beyond int32 or a negative uint is refused, not wrapped; a uint above int32's range is stored
  exactly; booleans inside a list read as 0 and 1; a scalar array's elements land at their stride.
"""
from __future__ import annotations

import json
import os
import struct
import sys
from pathlib import Path

import pytest

from rendering.native import loader

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "release" / "native_module"
BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()
HARNESS = ROOT / "native" / "core" / "python"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

pytestmark = pytest.mark.skipif(
    not BUILT,
    reason=f"the native core is not built in this checkout: no release/native_module/{loader.MODULE_NAME}.pyd",
)

PROBE_BLOCK = """#version 440
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 1) uniform Probe {
    mat4 m;
    mat3 n;
    float grid[2][3];
    int i;
    uint u;
    float f[4];
    vec4 v;
};
void main() { fragColor = vec4(m[0][0] + n[0][0] + grid[1][2] + float(i) + float(u) + f[3], v.yzw); }
"""


@pytest.fixture(scope="module")
def core():
    from rendering import native

    return native.load(MODULE_DIR)


@pytest.fixture(scope="module")
def probe_pack(tmp_path_factory):
    import probe_rings

    return probe_rings.bake(PROBE_BLOCK, "probe_block.frag", tmp_path_factory.mktemp("probe_block"))


def _members(facts: dict) -> dict:
    return {row[0]: row for row in facts["layout"]["members"]}


@pytest.mark.qt
def test_unpackable_members_are_always_unfilled_and_refused(core, probe_pack, qt_app):
    values = {"m": [float(k) for k in range(16)], "i": -3, "u": 4_000_000_000, "f": [1.0, 2.0, 3.0, 4.0],
              "v": [0.1, 0.2, 0.3, 0.4]}
    data, facts = core.program_block_pack(probe_pack, "Probe", values)
    assert sorted(facts["unfilled"]) == ["grid", "n"]
    rows = _members(facts)
    assert struct.unpack_from("<i", data, rows["i"][2])[0] == -3
    assert struct.unpack_from("<I", data, rows["u"][2])[0] == 4_000_000_000
    stride = rows["f"][4]
    assert stride >= 16 and [struct.unpack_from("<f", data, rows["f"][2] + k * stride)[0] for k in range(4)] == [
        1.0, 2.0, 3.0, 4.0]
    for name in ("n", "grid"):
        with pytest.raises(ValueError, match=name):
            core.program_block_pack(probe_pack, "Probe", {name: [0.0] * 6})


@pytest.mark.qt
def test_values_without_a_defined_conversion_are_refused_and_bools_in_lists_read(core, probe_pack, qt_app):
    pack = core.module.program_block_pack
    for raw in ('{"i": 3e10}', '{"i": -3e10}', '{"u": -1}', '{"u": 5e9}', '{"f": [1e39, 0, 0, 0]}'):
        with pytest.raises(ValueError):
            pack(probe_pack, "Probe", raw)
    data, facts = pack(probe_pack, "Probe", '{"f": [true, false, true, 2]}')
    rows = _members(json.loads(facts))
    stride = rows["f"][4]
    assert [struct.unpack_from("<f", data, rows["f"][2] + k * stride)[0] for k in range(4)] == [1.0, 0.0, 1.0, 2.0]


@pytest.mark.qt
def test_a_mode_is_packed_by_name_and_its_unknown_and_unfilled_members_refused(core, tmp_path, qt_app):
    import probe_rings as pr

    passes = pr.passes(tmp_path)
    settings = pr.resolve_settings({}, target_px=(480, 270), dpr=1.0)
    simulation = pr.RingsSimulation()
    values = [simulation.step(1.0 / 60.0) for _ in range(60)][-1]
    blocks, facts = core.mode_blocks(pr.SCHEMA, passes, settings, pr.record(values))
    assert [p["name"] for p in facts["program"]["passes"]] == ["rings", "glow"] and len(blocks) == 2
    frame_rows = {row[0]: row for p in facts["program"]["passes"] for row in p["frame"]["members"]}
    rings_frame = blocks[0][1]
    assert struct.unpack_from("<i", rings_frame, frame_rows["ring_count"][2])[0] == values["ring_count"]
    glow_frame = blocks[1][1]
    assert struct.unpack_from("<f", glow_frame, frame_rows["level"][2])[0] == struct.unpack(
        "<f", struct.pack("<f", values["level"]))[0]
    with pytest.raises(ValueError, match="u_glow"):
        core.mode_blocks(pr.SCHEMA, passes, {k: v for k, v in settings.items() if k != "u_glow"}, pr.record(values))
    with pytest.raises(ValueError, match="u_spare"):
        core.mode_blocks(pr.SCHEMA, passes, dict(settings, u_spare=1.0), pr.record(values))
    for name, bad in (("level", float("nan")), ("ring_count", 3_000_000_000)):
        broken = bytearray(pr.record(values))
        field = pr.SCHEMA.layout.field(name)
        struct.pack_into("<d" if field.kind == "f64" else "<I", broken, field.offset, bad)
        with pytest.raises(ValueError, match=name):
            core.mode_blocks(pr.SCHEMA, passes, settings, bytes(broken))
