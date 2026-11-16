"""GPU-free admission of resources shared by independently baked geometry stages."""
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
def bake(tmp_path_factory):
    import probe_rings
    folder = tmp_path_factory.mktemp("cross_stage_interface")
    return lambda source, name: probe_rings.bake(source, name, folder)


def _reflection(pack, path):
    from tools.regen_qrc import quick_shader_baker
    path.write_bytes(pack)
    dumped = subprocess.run([str(quick_shader_baker(sys.executable)), "--dump", str(path)],
                            check=True, capture_output=True, text=True, timeout=30).stdout
    return json.JSONDecoder().raw_decode(dumped.split("Reflection info:", 1)[1].lstrip())[0]


def _source(stage, kind, *, alias="", swapped=False, readwrite=False, present=True):
    if kind == "own":
        declaration = "layout(std140, binding = 2) uniform SharedOwn { %s }%s;"
        fields = "vec4 first; vec4 second;"
        value = "first + second"
    elif kind == "conventions":
        declaration = "layout(std140, binding = 17) uniform SrpssConventions { %s }%s;"
        fields = "vec2 srpssConventions; vec2 other;" if swapped else "vec4 srpssConventions;"
        value = "vec4(srpssConventions, other)" if swapped else "srpssConventions"
    else:
        declaration = "layout(std430, binding = 3) " + ("" if readwrite else "readonly ") + "buffer SharedStorage { %s }%s;"
        fields = "vec4 first; vec4 second;"
        value = "first + second"
    if swapped and kind != "conventions":
        fields = "vec4 second; vec4 first;"
    if alias:
        value = value.replace("first", alias + ".first").replace("second", alias + ".second")
        value = value.replace("srpssConventions", alias + ".srpssConventions").replace("other", alias + ".other")
    block = declaration % (fields, " " + alias if alias else "") if present else ""
    read = value if present else "vec4(0.0)"
    if stage == "vert":
        return "#version 440\n" + block + """
layout(location = 0) out vec2 vUv;
void main() {
    vec2 point = vec2(float((gl_VertexIndex << 1) & 2), float(gl_VertexIndex & 2));
    vUv = point;
    gl_Position = vec4(point * 2.0 - 1.0, 0.0, 1.0) + (""" + read + ") * 0.001;\n}\n"
    return "#version 440\n" + block + "\nlayout(location = 0) in vec2 vUv;\nlayout(location = 0) out vec4 fragColor;\nvoid main() { fragColor = " + read + " + vec4(vUv, 0.0, 1.0); }\n"


def _admit(vertex, fragment, kind, *, storage_names=("SharedStorage",), samplers=()):
    from rendering import native
    from rendering.native.mode import ModePass, ModeStream, PassGeometry, program_json, schema_table_entry
    import mesh_buffers as mb

    storage = tuple((name, "payload") for name in storage_names) if kind == "storage" else ()
    geometry = PassGeometry(vertex, vertices="count", instances=1, storage=storage)
    fields = (("count", "u32", 1),) + ((("payload", "f32", 8), ("payload_used", "u32", 1)) if storage else ())
    schema = mb.schema("cross_stage", fields,
                       (("payload_used", "at_most", 8),) if storage else (), code=250)
    streams = (ModeStream("payload", "payload", used="payload_used"),) if storage else ()
    declaration, shaders = program_json((ModePass("probe", fragment, "replace", geometry=geometry, samplers=samplers),), streams=streams)
    settings = {"first": [0.1, 0.2, 0.3, 0.4], "second": [0.5, 0.6, 0.7, 0.8]} if kind == "own" else {}
    record = {"count": 3}
    if storage:
        record.update(payload=struct.pack("<8f", *range(8)), payload_used=8)
    return native.load(MODULE_DIR).module.mode_blocks(
        json.dumps(schema_table_entry(schema)), declaration, shaders, json.dumps(settings),
        schema.encode(record), None, (64, 64))


@pytest.mark.parametrize("kind", ["own", "conventions", "storage"])
@pytest.mark.parametrize("shared", ["same", "aliases", "vertex_only", "fragment_only"])
def test_valid_shared_and_stage_only_resources_are_admitted(bake, tmp_path, kind, shared):
    built = [bake(_source(stage, kind, alias=(stage + "Data") if shared == "aliases" else "",
                          present=shared != ("fragment_only" if stage == "vert" else "vertex_only")),
                  f"{kind}_{shared}.{stage}") for stage in ("vert", "frag")]
    category = "storageBlocks" if kind == "storage" else "uniformBlocks"
    blocks = [_reflection(pack, tmp_path / f"{stage}.qsb").get(category, [])
              for stage, pack in zip(("vert", "frag"), built)]
    if shared in ("same", "aliases"):
        assert len(blocks[0]) == len(blocks[1]) == 1
        alias_key = "instanceName" if kind == "storage" else "structName"
        if shared == "aliases":
            assert blocks[0][0][alias_key] != blocks[1][0][alias_key]
        assert {k: v for k, v in blocks[0][0].items() if k != alias_key} == {
            k: v for k, v in blocks[1][0].items() if k != alias_key}
    else:
        assert [len(items) for items in blocks] == ([1, 0] if shared == "vertex_only" else [0, 1])
    _admit(*built, kind)


@pytest.mark.parametrize("kind,change", [("own", "offsets"), ("conventions", "members"),
                                         ("storage", "offsets"), ("storage", "access")])
def test_shared_resource_layout_mismatch_is_rejected(bake, tmp_path, kind, change):
    vertex = bake(_source("vert", kind), f"{kind}_{change}.vert")
    fragment = bake(_source("frag", kind, swapped=change != "access", readwrite=change == "access"),
                    f"{kind}_{change}.frag")
    category = "storageBlocks" if kind == "storage" else "uniformBlocks"
    original, changed = [_reflection(pack, tmp_path / f"{stage}.qsb")[category][0]
                         for stage, pack in (("vert", vertex), ("frag", fragment))]
    assert original["blockName"] == changed["blockName"]
    assert original["binding"] == changed["binding"]
    size_key = "knownSize" if kind == "storage" else "size"
    assert original[size_key] == changed[size_key]
    if change == "access":
        assert {k for k in original.keys() | changed.keys() if original.get(k) != changed.get(k)} == {"qualifierFlags"}
    else:
        assert original["members"] != changed["members"]
        if change == "offsets":
            assert {m["name"]: m["offset"] for m in original["members"]} != {
                m["name"]: m["offset"] for m in changed["members"]}
    with pytest.raises(ValueError, match=r"probe.*(shared|stage|layout|block)"):
        _admit(vertex, fragment, kind)



@pytest.mark.parametrize("shared", [True, False], ids=["shared", "vertex_only"])
def test_geometry_storage_must_be_read_only(bake, tmp_path, shared):
    vertex = bake(_source("vert", "storage", readwrite=True), f"writable_{shared}.vert")
    fragment = bake(_source("frag", "storage", readwrite=True, present=shared), f"writable_{shared}.frag")
    readonly = bake(_source("vert", "storage"), f"readonly_{shared}.vert")
    reference = _reflection(readonly, tmp_path / "readonly.qsb")["storageBlocks"][0]
    blocks = [_reflection(pack, tmp_path / f"{stage}.qsb").get("storageBlocks", [])
              for stage, pack in (("vert", vertex), ("frag", fragment))]
    assert [len(items) for items in blocks] == ([1, 1] if shared else [1, 0])
    assert reference["qualifierFlags"] != 0
    for block in (block for items in blocks for block in items):
        # qsb JSON omits the zero-valued (read/write) qualifier flags.
        assert block.get("qualifierFlags", 0) == 0
        assert {key for key in reference.keys() | block.keys() if reference.get(key) != block.get(key)} == {
            "qualifierFlags"}
    with pytest.raises(ValueError, match=r"probe.*(read.only|storage|buffer)"):
        _admit(vertex, fragment, "storage")


@pytest.mark.parametrize("collision", [False, True], ids=["distinct_bindings", "binding_collision"])
def test_distinct_stage_storage_blocks_need_distinct_bindings(bake, tmp_path, collision):
    vertex = bake(_source("vert", "storage"), f"distinct_{collision}.vert")
    fragment_source = _source("frag", "storage").replace("SharedStorage", "OtherStorage")
    if not collision:
        fragment_source = fragment_source.replace("binding = 3", "binding = 4")
    fragment = bake(fragment_source, f"distinct_{collision}.frag")
    blocks = [_reflection(pack, tmp_path / f"{stage}.qsb")["storageBlocks"][0]
              for stage, pack in (("vert", vertex), ("frag", fragment))]
    assert [block["blockName"] for block in blocks] == ["SharedStorage", "OtherStorage"]
    assert [block["binding"] for block in blocks] == ([3, 3] if collision else [3, 4])
    assert blocks[0]["qualifierFlags"] == blocks[1]["qualifierFlags"] != 0
    assert blocks[0]["members"] == blocks[1]["members"]
    if collision:
        with pytest.raises(ValueError, match=r"probe.*(binding|storage|buffer)"):
            _admit(vertex, fragment, "storage", storage_names=("SharedStorage", "OtherStorage"))
    else:
        _admit(vertex, fragment, "storage", storage_names=("SharedStorage", "OtherStorage"))



def _sampler_source(stage, *, dimensions=2, present=True):
    source = _source(stage, "conventions", present=False)
    if not present:
        return source
    declaration = f"layout(binding = 5) uniform sampler{dimensions}D sharedTexture;\n"
    coordinate = "vec2(0.25)" if dimensions == 2 else "vec3(0.25)"
    return source.replace("#version 440\n", "#version 440\n" + declaration).replace(
        "vec4(0.0)", f"texture(sharedTexture, {coordinate})")


@pytest.mark.parametrize("shared", ["same", "vertex_only", "fragment_only"])
def test_shared_and_stage_only_2d_samplers_are_admitted(bake, tmp_path, shared):
    from rendering.native.mode import PassSampler

    built = [bake(_sampler_source(stage, present=shared != (
                      "fragment_only" if stage == "vert" else "vertex_only")), f"sampler_{shared}.{stage}")
             for stage in ("vert", "frag")]
    images = [_reflection(pack, tmp_path / f"{stage}.qsb").get("combinedImageSamplers", [])
              for stage, pack in zip(("vert", "frag"), built)]
    assert [len(items) for items in images] == {
        "same": [1, 1], "vertex_only": [1, 0], "fragment_only": [0, 1]}[shared]
    for image in (image for items in images for image in items):
        assert image["name"] == "sharedTexture"
        assert image["binding"] == 5
        assert image["type"] == "sampler2D"
    if shared == "same":
        assert images[0] == images[1]
    _admit(*built, "sampler", samplers=(PassSampler("sharedTexture", "source"),))


def test_shared_sampler_dimension_mismatch_is_rejected(bake, tmp_path):
    from rendering.native.mode import PassSampler

    # Put 2D last: the old union overwrites the vertex's 3D dimension with it.
    built = [bake(_sampler_source(stage, dimensions=dimensions), f"sampler_mismatch.{stage}")
             for stage, dimensions in (("vert", 3), ("frag", 2))]
    images = [_reflection(pack, tmp_path / f"{stage}.qsb")["combinedImageSamplers"][0]
              for stage, pack in zip(("vert", "frag"), built)]
    assert [image["type"] for image in images] == ["sampler3D", "sampler2D"]
    assert {key for key in images[0].keys() | images[1].keys()
            if images[0].get(key) != images[1].get(key)} == {"type"}
    assert images[0]["name"] == images[1]["name"] == "sharedTexture"
    assert images[0]["binding"] == images[1]["binding"] == 5
    with pytest.raises(ValueError, match=r"probe.*sampler"):
        _admit(*built, "sampler", samplers=(PassSampler("sharedTexture", "source"),))
