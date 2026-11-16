"""GPU-free admission of a transparency pass's sorted shader interface."""
from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "native" / "core" / "python"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

from rendering.native import loader

MODULE_DIR = ROOT / "release" / "native_module"
pytestmark = pytest.mark.skipif(
    os.name != "nt" or not (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file(),
    reason="the built native module is required for the GPU-free admission oracle",
)


@pytest.fixture(scope="module")
def packs(tmp_path_factory):
    import post_stages
    import probe_rings

    folder = tmp_path_factory.mktemp("sorted_interface")
    oit = post_stages.layer_text(1, emission=False, sorted_pack=False, frag_depth=False)
    sorted_source = post_stages.layer_text(1, emission=False, sorted_pack=True, frag_depth=False)
    return oit, sorted_source, lambda source, name: probe_rings.bake(
        source, name if Path(name).suffix else name + ".frag", folder)


def _admit(oit, sorted_pack, *, geometry=None, streams=(), schema=None, record=None):
    from rendering import native
    from rendering.native.mode import (ModePass, ModeTarget, TargetAttachment, TransparencyTarget, TransparencyResolve,
                                       program_json, schema_table_entry)
    import mesh_buffers as mb

    schema = schema or mb.schema("sorted_interface", (("u_l1_band", "f64", 1),), code=250)
    owner = ModeTarget("scene", (TargetAttachment("colour", "rgba8"),), depth=True)
    target = TransparencyTarget("glass", "scene")
    passes = (ModePass("layer", oit, "replace", target="glass", sorted_pack=sorted_pack, geometry=geometry),
              TransparencyResolve("resolve", "glass"))
    declaration, shaders = program_json(passes, (owner, target), streams=streams)
    settings = {"u_l1_colour": [0.2, 0.4, 0.6, 0.8], "u_l1_disc": [0.5, 0.5, 0.3, 0.6],
                "u_l1_light": [0.1, 0.2, 0.3, 1.0]}
    return native.load(MODULE_DIR).module.mode_blocks(
        json.dumps(schema_table_entry(schema)), declaration, shaders, json.dumps(settings),
        schema.encode(record if record is not None else {"u_l1_band": 0.0}), None, (64, 64))


def _reflection(pack, path):
    from tools.regen_qrc import quick_shader_baker

    path.write_bytes(pack)
    dumped = subprocess.run([str(quick_shader_baker(sys.executable)), "--dump", str(path)],
                            check=True, capture_output=True, text=True, timeout=30).stdout
    return json.JSONDecoder().raw_decode(dumped.split("Reflection info:", 1)[1].lstrip())[0]


def test_real_oit_and_sorted_pair_is_admitted(packs):
    oit, sorted_source, bake = packs
    _admit(bake(oit, "oit"), bake(sorted_source, "sorted"))


@pytest.mark.parametrize("case,category", [("block_offsets", "blocks"), ("input_location", "inputs")])
def test_sorted_pack_must_match_interface(packs, case, category):
    oit, sorted_source, bake = packs
    if case == "block_offsets":
        old = "vec4 u_l1_colour;   // straight colour and alpha\n    vec4 u_l1_disc;"
        new = "vec4 u_l1_disc;   // straight colour and alpha\n    vec4 u_l1_colour;"
    else:
        old = "layout(location = 0) in vec2 vUv;"
        new = "layout(location = 1) in vec2 vUv;"
    assert sorted_source.count(old) == 1
    different = sorted_source.replace(old, new)
    oit_pack = bake(oit, "oit_" + case)
    sorted_pack = bake(different, "sorted_" + case)
    if case == "block_offsets":
        from rendering import native
        core = native.load(MODULE_DIR)
        plain, plain_facts = core.program_block_pack(oit_pack, "PostLayer1", {})
        changed, changed_facts = core.program_block_pack(sorted_pack, "PostLayer1", {})
        assert len(plain) == len(changed)
        assert plain_facts["layout"]["members"] != changed_facts["layout"]["members"]
    with pytest.raises(ValueError, match=r"sorted pack.*" + category):
        _admit(oit_pack, sorted_pack)


def test_equivalent_uniform_blocks_in_different_declaration_order_are_admitted(packs, tmp_path):
    oit, sorted_source, bake = packs
    import post_stages

    own = post_stages._LAYER_BLOCK % {"n": 1}
    conventions = "layout(std140, binding = 17) uniform SrpssConventions { vec4 srpssConventions; };\n"
    assert oit.count(own) == sorted_source.count(own) == 1
    oit = oit.replace(own, conventions + own)
    sorted_source = sorted_source.replace(own, own + conventions)
    # Keep the conventions block live in both shader reflections.
    oit = oit.replace("float alpha = u_l1_colour.a;", "float alpha = u_l1_colour.a + srpssConventions.x;")
    sorted_source = sorted_source.replace("void main()\n{", "void main()\n{\n    float conventionsFirst = srpssConventions.x;")
    sorted_source = sorted_source.replace("float alpha = u_l1_colour.a;", "float alpha = u_l1_colour.a + conventionsFirst;")
    oit_pack, sorted_pack = bake(oit, "oit_reordered"), bake(sorted_source, "sorted_reordered")
    orders = [[block["blockName"] for block in _reflection(pack, tmp_path / f"order{index}.qsb")["uniformBlocks"]]
              for index, pack in enumerate((oit_pack, sorted_pack))]
    assert orders == [["PostLayer1", "SrpssConventions"], ["SrpssConventions", "PostLayer1"]]
    _admit(oit_pack, sorted_pack)


def test_sorted_pack_rejects_extra_storage_image(packs):
    oit, sorted_source, bake = packs
    declaration = "layout(rgba32f, binding = 5) uniform readonly image2D extra;\n"
    sorted_source = sorted_source.replace("void main()", declaration + "void main()")
    old = "sceneTransparent(u_l1_colour.rgb * alpha, alpha, u_l1_light.w);"
    assert sorted_source.count(old) == 1
    sorted_source = sorted_source.replace(
        old, "sceneTransparent(u_l1_colour.rgb * alpha + imageLoad(extra, ivec2(0)).rgb, alpha, u_l1_light.w);")
    with pytest.raises(ValueError, match=r"sorted pack.*storage images"):
        _admit(bake(oit, "oit_image"), bake(sorted_source, "sorted_image"))


@pytest.fixture(scope="module")
def storage_pair(packs):
    from rendering.native.mode import ModeStream, PassGeometry
    import mesh_buffers as mb

    oit, sorted_source, bake = packs
    block = "layout(std430, binding = 3) readonly buffer SortedStorage { vec4 first; vec4 second; };\n"
    use = "sceneTransparent(u_l1_colour.rgb * alpha, alpha, u_l1_light.w);"
    read = "sceneTransparent(u_l1_colour.rgb * alpha + first.rgb + second.rgb, alpha, u_l1_light.w);"
    assert oit.count(use) == sorted_source.count(use) == 1
    oit = oit.replace("void main()", block + "void main()").replace(use, read)
    sorted_source = sorted_source.replace("void main()", block + "void main()").replace(use, read)
    vertex = """#version 440
layout(location = 0) out vec2 vUv;
void main() {
    vec2 point = vec2(float((gl_VertexIndex << 1) & 2), float(gl_VertexIndex & 2));
    vUv = point;
    gl_Position = vec4(point * 2.0 - 1.0, 0.0, 1.0);
}
"""
    geometry = PassGeometry(bake(vertex, "sorted_storage.vert"), vertices=3, instances=1,
                            storage=(("SortedStorage", "payload"),))
    schema = mb.schema("sorted_storage", (("u_l1_band", "f64", 1), ("payload", "f32", 8),
                                          ("payload_used", "u32", 1)), (("payload_used", "at_most", 8),), code=250)
    kwargs = dict(geometry=geometry, streams=(ModeStream("payload", "payload", used="payload_used"),),
                  schema=schema, record={"u_l1_band": 0.0, "payload": struct.pack("<8f", *([0.0] * 8)),
                                         "payload_used": 8})
    return bake(oit, "oit_storage"), sorted_source, bake, kwargs


def test_geometry_sorted_storage_pair_is_admitted(storage_pair):
    oit, sorted_source, bake, kwargs = storage_pair
    _admit(oit, bake(sorted_source, "sorted_storage_valid"), **kwargs)


def test_equivalent_sorted_storage_with_different_instance_aliases_is_admitted(packs, storage_pair, tmp_path):
    oit, sorted_source, bake = packs
    _, _, _, kwargs = storage_pair
    read = "sceneTransparent(u_l1_colour.rgb * alpha, alpha, u_l1_light.w);"
    built = []
    for source, alias in ((oit, "plainData"), (sorted_source, "sortedData")):
        block = f"layout(std430, binding = 3) readonly buffer SortedStorage {{ vec4 first; vec4 second; }} {alias};\n"
        assert source.count(read) == 1
        source = source.replace("void main()", block + "void main()").replace(
            read, f"sceneTransparent(u_l1_colour.rgb * alpha + {alias}.first.rgb + {alias}.second.rgb, alpha, u_l1_light.w);")
        built.append(bake(source, alias))
    blocks = [_reflection(pack, tmp_path / f"alias{index}.qsb")["storageBlocks"][0]
              for index, pack in enumerate(built)]
    assert blocks[0]["instanceName"] != blocks[1]["instanceName"]
    assert {key: value for key, value in blocks[0].items() if key != "instanceName"} == {
        key: value for key, value in blocks[1].items() if key != "instanceName"}
    _admit(*built, **kwargs)


def test_sorted_geometry_storage_members_must_match(storage_pair, tmp_path):
    oit, sorted_source, bake, kwargs = storage_pair
    old, new = "vec4 first; vec4 second;", "vec4 second; vec4 first;"
    assert sorted_source.count(old) == 1
    sorted_pack = bake(sorted_source.replace(old, new), "sorted_storage_offsets")
    original = _reflection(oit, tmp_path / "oit.qsb")["storageBlocks"]
    changed = _reflection(sorted_pack, tmp_path / "sorted.qsb")["storageBlocks"]
    assert len(original) == len(changed) == 1
    assert "knownSize" in original[0], original[0]
    assert original[0]["knownSize"] == changed[0]["knownSize"]
    assert original[0]["members"] != changed[0]["members"]
    with pytest.raises(ValueError, match=r"sorted pack.*storage blocks"):
        _admit(oit, sorted_pack, **kwargs)


def test_sorted_geometry_storage_access_must_match(storage_pair, tmp_path):
    oit, sorted_source, bake, kwargs = storage_pair
    assert sorted_source.count("readonly buffer SortedStorage") == 1
    sorted_pack = bake(sorted_source.replace("readonly buffer SortedStorage", "buffer SortedStorage"),
                       "sorted_storage_readwrite")
    original = _reflection(oit, tmp_path / "readonly.qsb")["storageBlocks"][0]
    changed = _reflection(sorted_pack, tmp_path / "readwrite.qsb")["storageBlocks"][0]
    differences = {key for key in original.keys() | changed.keys() if original.get(key) != changed.get(key)}
    assert differences == {"qualifierFlags"}, (original, changed)
    with pytest.raises(ValueError, match=r"sorted pack.*storage blocks"):
        _admit(oit, sorted_pack, **kwargs)
