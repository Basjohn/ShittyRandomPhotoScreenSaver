"""GPU-free canonical reserved-resource and supported descriptor-set admission."""
from __future__ import annotations

import pytest

from tests.test_native_cross_stage_interface import (
    MODULE_DIR, _admit, _reflection, _sampler_source, _source, bake, pytestmark,
)


def _conventions_source(stage, *, present=True, malformed=None):
    from rendering.gl_programs.conventions import SRPSS_CONVENTIONS_GLSL

    source = _source(stage, "conventions", present=False)
    if not present:
        return source
    if malformed is None:
        declaration, read = SRPSS_CONVENTIONS_GLSL, "srpssConventions"
    else:
        members, read = {
            "member_name": ("vec4 wrong;", "wrong"),
            "member_type": ("ivec4 srpssConventions;", "vec4(srpssConventions)"),
            "member_offset": ("vec4 padding; vec4 srpssConventions;", "padding + srpssConventions"),
            "block_size": ("vec4 srpssConventions; vec4 extra;", "srpssConventions + extra"),
            "array": ("vec4 srpssConventions[1];", "srpssConventions[0]"),
            "nested": ("Nested srpssConventions;", "srpssConventions.value"),
        }[malformed]
        prefix = "struct Nested { vec4 value; };\n" if malformed == "nested" else ""
        declaration = prefix + "layout(std140, binding = 17) uniform SrpssConventions { " + members + " };\n"
    return source.replace("#version 440\n", "#version 440\n" + declaration).replace("vec4(0.0)", read)


@pytest.mark.parametrize("stages", ["shared", "vertex_only", "fragment_only"])
def test_canonical_conventions_shared_and_stage_only_are_admitted(bake, tmp_path, stages):
    built = [bake(_conventions_source(stage, present=stages != (
                      "fragment_only" if stage == "vert" else "vertex_only")), f"canonical_{stages}.{stage}")
             for stage in ("vert", "frag")]
    blocks = [_reflection(pack, tmp_path / f"{stage}.qsb").get("uniformBlocks", [])
              for stage, pack in zip(("vert", "frag"), built)]
    assert [len(items) for items in blocks] == {
        "shared": [1, 1], "vertex_only": [1, 0], "fragment_only": [0, 1]}[stages]
    for block in (block for items in blocks for block in items):
        assert block["blockName"] == "SrpssConventions"
        assert block["binding"] == 17
        assert block["size"] == 16  # conventions.h::ConventionsBlock, one std140 vec4
        assert [(member["name"], member["type"], member["offset"]) for member in block["members"]] == [
            ("srpssConventions", "vec4", 0)]
    _admit(*built, "conventions")


@pytest.mark.parametrize("stage", ["vert", "frag"])
@pytest.mark.parametrize("malformed", ["member_name", "member_type", "member_offset", "block_size", "array", "nested"])
def test_malformed_stage_only_conventions_are_rejected(bake, tmp_path, stage, malformed):
    built = [bake(_conventions_source(current, present=current == stage, malformed=malformed),
                  f"bad_{stage}_{malformed}.{current}") for current in ("vert", "frag")]
    actual = _reflection(built[0 if stage == "vert" else 1], tmp_path / "bad.qsb")["uniformBlocks"][0]
    canonical = bake(_conventions_source(stage), f"canonical_{malformed}.{stage}")
    expected = _reflection(canonical, tmp_path / "canonical.qsb")["uniformBlocks"][0]
    assert actual["blockName"] == expected["blockName"] == "SrpssConventions"
    assert actual["binding"] == expected["binding"] == 17
    if malformed == "member_name":
        assert actual["members"][0]["name"] != expected["members"][0]["name"]
    elif malformed == "member_type":
        assert actual["members"][0]["type"] != expected["members"][0]["type"]
    elif malformed == "member_offset":
        assert next(member["offset"] for member in actual["members"]
                    if member["name"] == "srpssConventions") != expected["members"][0]["offset"]
    elif malformed == "block_size":
        assert actual["size"] != expected["size"]
    else:
        assert actual["size"] == expected["size"]
        assert actual["members"] != expected["members"]
    with pytest.raises(ValueError, match=r"probe.*(conventions|Conventions|reserved)"):
        _admit(*built, "conventions")


@pytest.mark.parametrize("kind", ["own", "conventions", "storage", "sampler"])
@pytest.mark.parametrize("stage", ["vert", "frag"])
@pytest.mark.parametrize("descriptor_set", [0, 1], ids=["supported_set0", "unsupported_set1"])
def test_resource_descriptor_set_admission(bake, tmp_path, kind, stage, descriptor_set):
    from rendering.native.mode import PassSampler

    source = _sampler_source if kind == "sampler" else lambda current, present: _source(current, kind, present=present)
    texts = [source(current, present=current == stage) for current in ("vert", "frag")]
    index = 0 if stage == "vert" else 1
    assert texts[index].count("binding = ") == 1
    texts[index] = texts[index].replace("binding = ", f"set = {descriptor_set}, binding = ")
    built = [bake(text, f"set{descriptor_set}_{kind}_{stage}.{current}")
             for current, text in zip(("vert", "frag"), texts)]
    category = {"own": "uniformBlocks", "conventions": "uniformBlocks", "storage": "storageBlocks",
                "sampler": "combinedImageSamplers"}[kind]
    resource = _reflection(built[index], tmp_path / "resource.qsb")[category][0]
    assert resource["set"] == descriptor_set, resource
    kwargs = {"samplers": (PassSampler("sharedTexture", "source"),)} if kind == "sampler" else {}
    if descriptor_set:
        with pytest.raises(ValueError, match=r"probe.*(descriptor|set)"):
            _admit(*built, kind, **kwargs)
    else:
        _admit(*built, kind, **kwargs)




def _admit_other_owner(bake, pack, *, compute=False, kind="conventions"):
    import json
    import mesh_buffers as mb
    from rendering import native
    from rendering.native.mode import (ComputeBinding, ComputePass, ModePass, PassGeometry, PassSampler,
                                       StorageBuffer, StorageImage, program_json, schema_table_entry)

    buffers, images, bindings = (), (), ()
    samplers = (PassSampler("sharedTexture", "source"),) if kind == "sampler" else ()
    if compute:
        buffers = (StorageBuffer("sink", 16),)
        bindings = (ComputeBinding("Sink", "sink", "buffer", "write"),)
        if kind == "storage":
            buffers += (StorageBuffer("source", 32),)
            bindings += (ComputeBinding("SharedStorage", "source", "buffer", "read"),)
        elif kind == "image":
            images = (StorageImage("source", (2, 2), "rgba32f"),)
            bindings += (ComputeBinding("sourceImage", "source", "image", "read"),)
        probe = ComputePass("probe", pack, bindings=bindings, groups=(1, 1, 1), samplers=samplers)
    else:
        probe = ModePass("probe", pack, "replace", samplers=samplers)
    # A separate legal draw consumes the test's count record field for either owner.
    vertex = bake(_source("vert", "conventions", present=False), "owner_control.vert")
    fragment = bake(_source("frag", "conventions", present=False), "owner_control.frag")
    draw = ModePass("control", fragment, "replace", geometry=PassGeometry(vertex, vertices="count", instances=1))
    declaration, shaders = program_json((probe, draw), buffers=buffers, images=images)
    schema = mb.schema("reserved_owners", (("count", "u32", 1),), code=250)
    settings = {"first": [0.1, 0.2, 0.3, 0.4], "second": [0.5, 0.6, 0.7, 0.8]} if kind == "own" else {}
    return native.load(MODULE_DIR).module.mode_blocks(
        json.dumps(schema_table_entry(schema)), declaration, shaders, json.dumps(settings),
        schema.encode({"count": 3}), None, (64, 64))


@pytest.mark.parametrize("malformed", [None, "member_name", "member_type", "member_offset", "block_size", "array", "nested"])
def test_fullscreen_conventions_shape_admission(bake, tmp_path, malformed):
    pack = bake(_conventions_source("frag", malformed=malformed), f"fullscreen_{malformed}.frag")
    block = _reflection(pack, tmp_path / "fullscreen.qsb")["uniformBlocks"][0]
    assert block["blockName"] == "SrpssConventions" and block["binding"] == 17
    if malformed:
        with pytest.raises(ValueError, match=r"probe.*(conventions|Conventions|reserved)"):
            _admit_other_owner(bake, pack)
    else:
        _admit_other_owner(bake, pack)


def test_stage_local_conventions_alias_is_admitted(bake, tmp_path):
    built = []
    blocks = []
    for stage in ("vert", "frag"):
        source = _source(stage, "conventions", alias=stage + "Conventions")
        pack = bake(source, f"canonical_alias.{stage}")
        built.append(pack)
        blocks.append(_reflection(pack, tmp_path / f"{stage}.qsb")["uniformBlocks"][0])
    assert blocks[0]["structName"] != blocks[1]["structName"]
    assert {k: v for k, v in blocks[0].items() if k != "structName"} == {
        k: v for k, v in blocks[1].items() if k != "structName"}
    _admit(*built, "conventions")


@pytest.mark.parametrize("owner,kind", [("fullscreen", "own"), ("fullscreen", "conventions"),
                                      ("fullscreen", "sampler"), ("compute", "own"),
                                      ("compute", "storage"), ("compute", "image"), ("compute", "sampler")])
@pytest.mark.parametrize("descriptor_set", [0, 1], ids=["supported_set0", "unsupported_set1"])
def test_fullscreen_and_compute_descriptor_set_admission(bake, tmp_path, owner, kind, descriptor_set):
    if owner == "fullscreen":
        source = _sampler_source("frag") if kind == "sampler" else _source("frag", kind)
        category = "combinedImageSamplers" if kind == "sampler" else "uniformBlocks"
        suffix = "frag"
    else:
        declaration, read, category = {
            "own": ("layout(std140, binding = 2) uniform SharedOwn { vec4 first; vec4 second; };", "first + second", "uniformBlocks"),
            "storage": ("layout(std430, binding = 3) readonly buffer SharedStorage { vec4 first; vec4 second; };", "first + second", "storageBlocks"),
            "image": ("layout(rgba32f, binding = 3) uniform readonly image2D sourceImage;", "imageLoad(sourceImage, ivec2(0))", "storageImages"),
            "sampler": ("layout(binding = 5) uniform sampler2D sharedTexture;", "texture(sharedTexture, vec2(0.25))", "combinedImageSamplers"),
        }[kind]
        source = "#version 440\nlayout(local_size_x = 1) in;\n" + declaration + "\n" + (
            "layout(std430, binding = 6) writeonly buffer Sink { vec4 value; };\nvoid main() { value = " + read + "; }\n")
        suffix = "comp"
    # Change only the resource under examination; the compute write sink stays in set0.
    source = source.replace("binding = ", f"set = {descriptor_set}, binding = ", 1)
    pack = bake(source, f"{owner}_{kind}_set{descriptor_set}.{suffix}")
    resources = _reflection(pack, tmp_path / "owner.qsb")[category]
    resource = next(resource for resource in resources if resource.get("blockName") != "Sink")
    assert resource["set"] == descriptor_set
    if descriptor_set:
        with pytest.raises(ValueError, match=r"probe.*(descriptor|set)"):
            _admit_other_owner(bake, pack, compute=owner == "compute", kind=kind)
    else:
        _admit_other_owner(bake, pack, compute=owner == "compute", kind=kind)

