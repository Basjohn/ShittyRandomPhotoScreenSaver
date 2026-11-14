"""N2.9's generic mode content and the audit's program-block edges (14 Nov, L2) on the built module, GPU-free.

The module is compiled only on GitHub; without ``release/native_module`` these tests skip and say so. The drawn proof
is ``native/core/python/generic_mode_check.py`` (its ``blocks`` round holds the full refusal table).

- ``mode_blocks``: Probe Rings' core members (from the card and the target), settings and record packed by name into
  each pass's one block; a setting left out, an unknown one, one naming a core member, no card, a value without a
  defined conversion (NaN, an int beyond int32) are refused. The core's conventions table is the face's.
- The product 2D packs (audit N29 M5): Oscilloscope and Spline Curve admitted, Bubble refused while its samplers are
  unbound and admitted with them bound (N4.a); a block at binding 17 (M3), a second block and an unbound sampler
  refused.
- N4.a: the seven fullscreen transitions' own packs admitted with uOldTex and uNewTex bound (vUv, one pass block), each
  refused unbound; an unknown, doubly bound, conventions-binding or block-binding sampler and an unknown mip filter
  refused.
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
    settings = pr.resolve_settings({}, dpr=1.5)
    card = pr.harness_card((480, 270), 1.5, fade=0.75)
    target = (720, 405)
    simulation = pr.RingsSimulation()
    values = [simulation.step(1.0 / 60.0) for _ in range(60)][-1]
    record = pr.record(values)
    blocks, facts = core.mode_blocks(pr.SCHEMA, passes, settings, record, card, target)
    assert [p["name"] for p in facts["program"]["passes"]] == ["rings", "glow"] and len(blocks) == 2
    # One block of its own per pass, each member filled by name from one source (audit N29 M5).
    for program_pass, sources, data in zip(facts["program"]["passes"], facts["passes"], blocks):
        rows = {row[0]: row for row in program_pass["block"]["members"]}
        assert program_pass["block"]["name"] == "ProbeRingsDraw" and program_pass["block"]["binding"] == 18
        assert sources["sources"]["u_target_px"] == "core" and sources["sources"]["u_fade"] == "core"
        assert struct.unpack_from("<2f", data, rows["u_target_px"][2]) == (720.0, 405.0)   # the target's pixels
        assert struct.unpack_from("<f", data, rows["u_fade"][2])[0] == 0.75                # the card's fade
        assert sources["sources"]["pulse_color"] == "record"
    assert facts["program"]["passes"][1]["uv"] == "v_uv" and facts["program"]["passes"][0]["conventions"] is True
    assert facts["program"]["passes"][0]["uv"] == ""                                     # rings reads no uv
    rows = {row[0]: row for row in facts["program"]["passes"][0]["block"]["members"]}
    assert struct.unpack_from("<i", blocks[0], rows["ring_count"][2])[0] == values["ring_count"]
    assert struct.unpack_from("<f", blocks[0], rows["u_thickness_px"][2])[0] == settings["u_thickness_px"]
    with pytest.raises(ValueError, match="u_glow"):
        core.mode_blocks(pr.SCHEMA, passes, {k: v for k, v in settings.items() if k != "u_glow"}, record, card, target)
    with pytest.raises(ValueError, match="u_spare"):
        core.mode_blocks(pr.SCHEMA, passes, dict(settings, u_spare=1.0), record, card, target)
    with pytest.raises(ValueError, match="core member"):
        core.mode_blocks(pr.SCHEMA, passes, dict(settings, u_fade=1.0), record, card, target)
    with pytest.raises(ValueError, match="card"):
        core.mode_blocks(pr.SCHEMA, passes, settings, record, None, target)
    for name, bad in (("level", float("nan")), ("ring_count", 3_000_000_000)):
        broken = bytearray(record)
        field = pr.SCHEMA.layout.field(name)
        struct.pack_into("<d" if field.kind == "f64" else "<I", broken, field.offset, bad)
        with pytest.raises(ValueError, match=name):
            core.mode_blocks(pr.SCHEMA, passes, settings, bytes(broken), card, target)


@pytest.mark.qt
def test_the_cores_conventions_are_the_faces(core, qt_app):
    from rendering.native.mode import MODE_CORE_MEMBERS

    assert core.mode_core_members() == MODE_CORE_MEMBERS


def _bumped(value):
    if isinstance(value, list):
        return [v + 1.25 for v in value]
    if isinstance(value, int):
        return (value + 1) % 4                       # the quarters
    return value + 0.25


def test_each_core_member_reads_its_own_values_and_moves_only_with_the_card_or_the_target(core, qt_app):
    # Audit N29 round 2, L6: every row of the conventions carries its own values. A member read from the card moves
    # with some key of the card and never with the target; a member of the core's own does not move with the card. A
    # name the core does not fill is refused (KeyError), never read as zeros.
    from rendering.native.mode import MODE_CARD_KEYS, MODE_CORE_MEMBERS

    card = {"quarters": 1, "item_size": [300.0, 160.0], "oriented_size": [160.0, 300.0], "dpr": 1.5,
            "content_fade": 0.5, "border_width": 2.0, "window_from_target": [0.0, 1.0, 10.0, -1.0, 0.0, 470.0],
            "item_from_window": [0.0, 0.5, -3.0, -0.5, 0.0, 260.0]}
    assert set(card) == set(MODE_CARD_KEYS)
    target = (451, 243)
    for name, (components, from_card) in MODE_CORE_MEMBERS.items():
        base = core.mode_core_values(name, card, target)
        assert len(base) == components, name
        moved_by = {key for key in card
                    if core.mode_core_values(name, {**card, key: _bumped(card[key])}, target) != base}
        assert bool(moved_by) == from_card, (name, moved_by)
        if from_card:
            assert core.mode_core_values(name, card, (target[0] + 3, target[1] + 5)) == base, name
    with pytest.raises(KeyError):
        core.mode_core_values("u_not_a_core_member", card, target)
    # Control: a card-derived member is not constant (the check above can see a row that zero-fills).
    assert core.mode_core_values("u_fade", card, target) != core.mode_core_values("u_fade", {**card, "content_fade": 0.0},
                                                                                     target)


@pytest.mark.qt
def test_the_product_2d_packs_are_admitted_and_bubble_with_its_samplers_bound(core, tmp_path, qt_app):
    # Audit N29 M5: the generic pass takes the product 2D shaders' shape, over their real .qsb packs. N4.a: Bubble's
    # two samplers are refused unbound and admitted bound by name to the item's textures.
    import generic_mode_check as check
    import probe_rings as pr
    from rendering.native.mode import ModePass, PassSampler
    from rendering.native.program_values import mode_fragment_pack
    from tools import regen_qrc

    for mode_id in ("oscilloscope", "devcurve"):
        layout = core.mode_program_layout([ModePass(mode_id, mode_fragment_pack(mode_id))])
        (program_pass,) = layout["passes"]
        assert program_pass["uv"] == "v_uv" and program_pass["block"]["binding"] != 17
    with pytest.raises(ValueError, match="unbound"):
        core.mode_program_layout([ModePass("bubble", mode_fragment_pack("bubble"))])
    declared = check.bubble_samplers()                      # Bubble's own names and bindings (round 2, L7)
    bound = tuple(PassSampler(name, f"texture_{index}") for index, (name, _binding) in enumerate(declared))
    (bubble,) = core.mode_program_layout([ModePass("bubble", mode_fragment_pack("bubble"), samplers=bound)])["passes"]
    assert len(declared) == 2 and {(s["name"], s["texture"], s["binding"]) for s in bubble["samplers"]} == {
        (name, f"texture_{index}", binding) for index, (name, binding) in enumerate(declared)}
    # Control: Bubble with its two samplers taken out is admitted with none bound (its samplers alone were refused).
    text = check.bubble_without_samplers_text((regen_qrc.mode_shader_dir() / "bubble.frag").read_text(encoding="utf-8"))
    stripped = pr.bake(text, "bubble.frag", tmp_path / "bubble")
    assert core.mode_program_layout([ModePass("bubble", stripped)])["passes"][0]["block"]["name"] == "BubbleDraw"


@pytest.mark.qt
def test_the_fullscreen_transitions_are_admitted_with_their_pictures_bound(core, tmp_path, qt_app):
    # N4.a: the seven fullscreen transitions' own fragments (vUv, one pass block, uOldTex and uNewTex), as they are.
    import fullscreen_pass_check as check
    from rendering.native.mode import ModePass

    for transition_id in check.FULLSCREEN_TRANSITIONS:
        program = check.transition_pass(transition_id, tmp_path / transition_id)
        (layout,) = core.mode_program_layout([program])["passes"]
        assert layout["uv"] == "vUv" and layout["block"]["binding"] == 18, transition_id
        assert {(s["name"], s["texture"]) for s in layout["samplers"]} == {("uOldTex", "old"), ("uNewTex", "new")}
        members = {row[0] for row in layout["block"]["members"]}
        assert "u_resolution" not in members, transition_id          # the core member's meaning differs: u_target_px
        # Control: the same pack with no samplers bound is refused.
        with pytest.raises(ValueError, match="unbound"):
            core.mode_program_layout([ModePass(program.name, program.pack, program.blend)])


@pytest.mark.qt
def test_an_unknown_doubly_bound_or_misplaced_sampler_is_refused(core, tmp_path, qt_app):
    import fullscreen_pass_check as check
    from rendering.native.mode import ModePass, PassSampler

    program = check.transition_pass("crossfade", tmp_path / "crossfade")
    old, new = program.samplers

    def layout(samplers, pack=program.pack):
        return core.mode_program_layout([ModePass(program.name, pack, program.blend, samplers=tuple(samplers))])

    with pytest.raises(ValueError, match="unknown"):
        layout([old, new, PassSampler("uMissing", "old")])
    with pytest.raises(ValueError, match="doubly bound"):
        layout([old, new, PassSampler("uOldTex", "new")])
    with pytest.raises(ValueError, match="unbound"):
        layout([old])
    for kind, word in (("binding17", "17"), ("block_binding", "own block"), ("shared_binding", "doubly bound")):
        with pytest.raises(ValueError, match=word):
            layout([old, new], pack=check.bake(check.sampler_variant_text(kind), f"{kind}.frag", tmp_path / kind))
    with pytest.raises(ValueError, match="mips"):
        core.module.mode_program_layout(json.dumps({"passes": [{"name": "x", "blend": "replace", "samplers": [
            {"name": "uOldTex", "texture": "old", "filter": "linear", "wrap": "clamp", "mips": "trilinear"}]}]}),
            [program.pack])
    # Control: both bound, as declared, are admitted.
    assert [s["binding"] for s in layout([old, new])["passes"][0]["samplers"]] == [0, 1]


@pytest.mark.qt
def test_a_pass_block_at_the_conventions_binding_or_a_second_block_is_refused(core, tmp_path, qt_app):
    # Audit N29 M3: binding 17 is the conventions block's whether or not the pass declares it.
    import generic_mode_check as check
    import probe_rings as pr
    from rendering.native.mode import ModePass

    def layout(kind):
        return core.mode_program_layout([ModePass("glow", pr.bake(check.variant_text(kind), "glow.frag",
                                                                  tmp_path / kind), "add")])

    with pytest.raises(ValueError, match="17 is the conventions block's"):
        layout("binding17")
    with pytest.raises(ValueError, match="one block of its own"):
        layout("two_blocks")
    with pytest.raises(ValueError, match="primitive"):
        layout("sampler")
    # Control: the glow pass as it is, at binding 18, is admitted.
    assert core.mode_program_layout(pr.passes(tmp_path / "base", only=("glow",)))["passes"][0]["block"]["binding"] == 18
