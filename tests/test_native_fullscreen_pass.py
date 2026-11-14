"""N4.a, the fullscreen pass and image sampling as a primitive (native/core/src/mode_content.*, shaders/mode.vert;
rendering/native/mode.py; the harness native/core/python/fullscreen_pass_check.py): everything that runs without the
built module. The built module's half is tests/test_native_core_mode.py and the harness's rounds.

- The seven fullscreen transitions' own fragments are in the shape the core admits: ``vUv`` at location 0, the two
  pictures ``uOldTex`` and ``uNewTex`` as sampler2Ds, one pass block whose every member the Python renderer fills, and
  no member that names a core member with another meaning (``u_resolution``: the core's logical size; the transitions'
  target pixels are ``u_target_px``).
- The core's triangle gives each quad's uv by the name the Python quads give it (derived from their vertex sources).
- The harness splits ``FullscreenPassRenderer.block_values`` into the core's members, the settings and the record, each
  member exactly once; its record's mode is never registered.
- The face declares samplers only for a pass that binds them, and refuses an unknown sampler state.
- The harness's measures (equality, the digest) see a one-level change and a flipped picture.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native" / "core"
HARNESS = CORE / "python"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

import fullscreen_pass_check as check  # noqa: E402  (native/core/python)

_SAMPLER = re.compile(r"layout\s*\(\s*binding\s*=\s*(\d+)\s*\)\s*uniform\s+sampler2D\s+(\w+)\s*;")
_INPUT = re.compile(r"layout\s*\(\s*location\s*=\s*(\d+)\s*\)\s*in\s+vec2\s+(\w+)\s*;")
_BLOCK = re.compile(r"layout\s*\(\s*std140\s*,\s*binding\s*=\s*(\d+)\s*\)\s*uniform\s+(\w+)\s*\{")


def _code(text: str) -> str:
    return re.sub(r"//[^\n]*", "", text)


def shape(text: str) -> dict:
    """What a fragment declares, as the core's checkPass reads its reflection."""
    code = _code(text)
    return {"inputs": _INPUT.findall(code), "samplers": sorted((name, int(b)) for b, name in _SAMPLER.findall(code)),
            "blocks": [(name, int(b)) for b, name in _BLOCK.findall(code) if name != "SrpssConventions"]}


def meaning_clashes(members, filled_by_python) -> list[str]:
    """Members the core fills (its conventions) that the Python renderer fills with another value: u_resolution (the
    core's logical size) where a transition meant its pixels. The two that agree by definition are excluded: uMatrix
    (no fragment reads it) and uItemSize (the logical size, on both sides); u_target_px is the target's pixels on both."""
    from rendering.native.mode import MODE_CORE_MEMBERS

    agreeing = {"uMatrix", "uItemSize", "u_target_px"}
    return [name for name in members if name in MODE_CORE_MEMBERS and name not in agreeing and name in filled_by_python]


def test_the_seven_fullscreen_transitions_are_in_the_shape_the_core_admits():
    from rendering.quick.transitions.fullscreen_pass import COMMON_VALUES

    for transition_id in check.FULLSCREEN_TRANSITIONS:
        cls = check.renderer_class(transition_id)
        declared = shape(cls.fragment_source)
        assert declared["inputs"] == [("0", "vUv")], transition_id
        assert declared["samplers"] == [("uNewTex", 1), ("uOldTex", 0)], transition_id
        assert declared["blocks"] == [(check.block_name(transition_id), 18)], transition_id
        members = check.block_members(transition_id)
        assert members[:3] == list(COMMON_VALUES), transition_id
        assert set(members) == set(COMMON_VALUES) | set(cls.value_names), transition_id
        assert meaning_clashes(members, set(COMMON_VALUES) | set(cls.value_names)) == [], transition_id
    # Negative control: a transition still naming its pixels u_resolution is a clash.
    assert meaning_clashes(["uMatrix", "u_progress", "u_resolution"], {"uMatrix", "u_progress", "u_resolution"}) == [
        "u_resolution"]


def test_the_cores_triangle_gives_each_quad_its_uv_by_the_python_quads_names():
    from rendering.gl_programs.item_quad import item_quad_vertex_source
    from rendering.quick.visualizer.render_contract import quick_visualizer_vertex_source

    def out_name(source: str) -> str:
        (name,) = re.findall(r"layout\s*\(\s*location\s*=\s*0\s*\)\s*out\s+vec2\s+(\w+)\s*;", source)
        return name

    visualizer, item = out_name(quick_visualizer_vertex_source("")), out_name(item_quad_vertex_source(""))
    cpp = (CORE / "src" / "mode_content.cpp").read_text(encoding="utf-8")
    assert re.search(r'kUvDownName\[\]\s*=\s*"(\w+)"', cpp).group(1) == visualizer
    assert re.search(r'kUvUpName\[\]\s*=\s*"(\w+)"', cpp).group(1) == item
    # The Python quads' conventions: the Visualizer quad's uv is the position (y down), the item quad's flips y.
    assert "v_uv = logicalUvFromPhysicalUv(aPosition);" in quick_visualizer_vertex_source("")
    assert "vUv = vec2(aPosition.x, 1.0 - aPosition.y);" in item_quad_vertex_source("")
    # The core's vertex stage passes the uv the pipeline feeds it (location 1) through at location 0.
    vert = _code((CORE / "shaders" / "mode.vert").read_text(encoding="utf-8"))
    assert "layout(location = 1) in vec2 uv;" in vert and "v_uv = uv;" in vert
    assert "layout(location = 0) out vec2 v_uv;" in vert
    # Negative control: a renamed output of a Python quad is seen.
    assert out_name(item_quad_vertex_source("").replace("out vec2 vUv;", "out vec2 vTex;")) != item


def _frame_values(transition_id: str, overrides=None, size=(320, 180)) -> dict:
    from PIL import Image

    images = tuple(Image.new("RGBA", size, (40 * k, 80, 120, 255)) for k in (1, 2))
    label = f"test_{transition_id}_{json.dumps(overrides or {}, sort_keys=True)}"    # the harness caches by label
    return check._values(transition_id, overrides or {}, images, size, {}, label)


def test_the_harness_fills_every_member_once_from_the_renderers_own_values():
    from rendering.native.mode import MODE_CORE_MEMBERS

    for variant, overrides in check.VARIANTS.items():
        transition_id = "burn" if variant.startswith("burn") else variant
        values = _frame_values(transition_id, overrides)
        members = check.block_members(transition_id)
        for progress in check.PROGRESS:
            core_values, settings, record = check.split_values(transition_id, values[progress])
            assert sorted([*core_values, *settings, *record]) == sorted(members), variant
            assert set(record) == set(check.per_frame_members(transition_id))
            assert not set(settings) & set(MODE_CORE_MEMBERS)
        # Settings are constant over the run (packed when they change: once); the record moves.
        settings_over_run = {json.dumps(check.split_values(transition_id, values[p])[1], sort_keys=True,
                                        default=list) for p in check.PROGRESS}
        assert len(settings_over_run) == 1, variant
        progress_over_run = {check.split_values(transition_id, values[p])[2]["u_progress"] for p in check.PROGRESS}
        assert len(progress_over_run) > 3, variant
    # The options variant really changes Burn's settings (the widened values are not the defaults again).
    default = check.split_values("burn", _frame_values("burn")[0.5])[1]
    options = check.split_values("burn", _frame_values("burn", check.VARIANTS["burn_options"])[0.5])[1]
    assert default != options and options["u_flames"] == 1 and options["u_direction"] == 4


def test_the_harness_record_is_the_per_frame_members_and_its_mode_is_never_registered(monkeypatch):
    from core.visualizer_engine import native_schema, packet_abi

    assert check.MODE_CODE not in packet_abi.MODE_CODES.values() and check.MODE_ID not in packet_abi.MODE_CODES
    for transition_id in check.PROVED:
        schema = check.frame_schema(transition_id)
        assert schema.fields == check.per_frame_members(transition_id)
        assert schema.mode_code == check.MODE_CODE and schema.schema_id not in native_schema.native_schemas()
        values = {name: 0.25 * (index + 1) for index, name in enumerate(schema.fields)}
        assert schema.decode(schema.encode(values)) == values
    assert check.frame_schema("crossfade").fields == ("u_progress",)
    assert check.frame_schema("burn").fields == ("u_progress", "u_time")
    assert check.frame_schema("crossfade").schema_id != check.frame_schema("burn").schema_id
    # Negative control: a stand-in registration of the harness's code is seen.
    monkeypatch.setattr(packet_abi, "MODE_CODES", {**packet_abi.MODE_CODES, check.MODE_ID: check.MODE_CODE})
    assert check.MODE_CODE in packet_abi.MODE_CODES.values()


def test_block_values_is_the_renderers_one_owner_of_its_values():
    from rendering.quick.transitions import fullscreen_pass

    source = Path(fullscreen_pass.__file__).read_text(encoding="utf-8")
    render = source.split("    def render(self", 1)[1].split("\n    def ", 1)[0]
    assert "pack_block(self._layout, self.block_values(frame))" in render
    assert "self.values(" not in render                          # values come through block_values only
    for transition_id in check.PROVED:
        values = _frame_values(transition_id)[0.5]
        assert set(values) == set(check.block_members(transition_id))


def test_the_face_declares_samplers_only_for_a_pass_that_binds_them():
    from rendering.native.mode import ModePass, PassSampler, program_json

    plain = ModePass("glow", b"x", "add")
    bound = ModePass("crossfade", b"y", "replace", check.samplers())
    declared, packs = program_json([plain, bound])
    passes = json.loads(declared)["passes"]
    assert passes[0] == {"name": "glow", "blend": "add"}                # N2.9's declaration as it was
    assert passes[1]["samplers"] == [
        {"name": "uOldTex", "texture": "old", "filter": "linear", "wrap": "clamp", "mips": "none"},
        {"name": "uNewTex", "texture": "new", "filter": "linear", "wrap": "clamp", "mips": "none"}]
    assert packs == [b"x", b"y"]
    assert [s.mips for s in check.samplers(old_mips="linear")] == ["linear", "none"]
    for bad in ({"filter": "cubic"}, {"wrap": "border"}, {"mips": "trilinear"}):
        with pytest.raises(ValueError):
            PassSampler("uOldTex", "old", **bad)


def test_the_harness_measures_see_a_level_and_a_flip():
    import numpy as np

    rng = np.random.default_rng(4)
    picture = rng.integers(0, 256, size=(36, 64, 4), dtype=np.uint8)
    assert check.compare(picture, picture.copy())["equal"]
    nudged = picture.copy()
    nudged[5, 7, 1] = (int(nudged[5, 7, 1]) + 1) % 256
    result = check.compare(nudged, picture)
    assert not result["equal"] and result["differing_pixels"] == 1 and result["max_level"] in (1, 255)
    flipped = picture[::-1].copy()
    assert not check.compare(flipped, picture)["equal"] and check.digest(flipped) != check.digest(picture)
    assert check.digest(picture) == check.digest(picture.copy())


def test_the_harness_shaders_bake_with_no_module_build(tmp_path):
    from tools import regen_qrc

    try:
        regen_qrc.quick_shader_baker(sys.executable)
    except regen_qrc.QrcRegenerationError as exc:
        pytest.skip(f"no qsb: {exc}")
    for transition_id in check.FULLSCREEN_TRANSITIONS:
        assert check.transition_pass(transition_id, tmp_path / transition_id).pack
    for kind in check.SAMPLER_VARIANTS:                                 # every one compiles: refused by checkPass
        text = check.sampler_variant_text(kind)
        assert text != check.renderer_class("crossfade").fragment_source
        assert check.bake(text, "crossfade.frag", tmp_path / kind)
    swapped = check.swapped_crossfade_text()
    assert "mix(newColor, oldColor, t)" in swapped and check.bake(swapped, "crossfade.frag", tmp_path / "swapped")
    # Negative control: a variant of a line the shader does not hold is refused, not silently passed.
    with pytest.raises(ValueError):
        check._replaced("void main() {}", "uOldTex", "uNewTex")


def test_the_default_photos_are_real_wallpapers():
    missing = [p for p in check.PHOTOS if not p.is_file()]
    if missing:
        pytest.skip(f"the PERSONALSET wallpapers are not on this machine: {missing}")
    from PIL import Image

    pictures = check.photos(check.PHOTOS, (64, 36))
    assert all(p.size == (64, 36) and p.mode == "RGBA" for p in pictures)
    assert pictures[0].tobytes() != pictures[1].tobytes()
    assert all(Image.open(p).size[0] >= 1280 for p in check.PHOTOS)
