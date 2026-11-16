"""GPU-free unsigned record-vector packing and portable uniform-array admission.

Qt 6.12 OpenGL uploads only element zero of unsigned/bool uniform arrays. CPU layout
introspection and storage-buffer arrays remain independent of this portable draw restriction.
"""
from __future__ import annotations

import json
import struct

import pytest

from tests.test_native_cross_stage_interface import MODULE_DIR, _reflection, _source, bake, pytestmark


@pytest.fixture(scope="module")
def core():
    from rendering import native
    return native.load(MODULE_DIR)


def _record_block(core, bake, declaration, count, *, kind="u32", checks=(), values=None):
    import mesh_buffers as mb
    from rendering.native.mode import ModePass

    source = "#version 440\nlayout(std140, binding = 2) uniform Probe { " + declaration + " };\n"
    source += "layout(location = 0) out vec4 fragColor;\nvoid main() { fragColor = vec4(float(words"
    source += "[0]" * declaration.count("[")
    source += ".x" if "vec" in declaration else ""
    source += ")); }\n"
    pack = bake(source, "record_probe.frag")
    schema = mb.schema("unsigned_record", (("words", kind, count),), checks, code=250)
    if values is None:
        values = ([0, 0xFFFFFFFF, 0x80000000, 34114] * 2)[:count]
    record = {"words": values[0] if count == 1 else values}
    blocks, facts = core.mode_blocks(schema, (ModePass("probe", pack, "replace"),), {},
                                     schema.encode(record), None, (64, 64))
    member = facts["program"]["passes"][0]["block"]["members"][0]
    return blocks[0], member


@pytest.mark.parametrize("components", [2, 3, 4])
@pytest.mark.parametrize("array_one", [False, True], ids=["vector", "array_of_one_vector"])
def test_u32_sequence_fills_one_matching_unsigned_vector(core, bake, components, array_one):
    values = [0xFFFFFFFF, 0x80000000, 0, 34114][:components]
    data, member = _record_block(core, bake, f"uvec{components} words{'[1]' if array_one else ''};",
                                 components, values=values)
    assert member[3] == 1
    assert struct.unpack_from(f"<{components}I", data, member[2]) == tuple(values)


@pytest.mark.parametrize("declaration,count,kind", [
    ("uvec2 words;", 1, "u32"), ("uvec2 words;", 3, "u32"),
    ("uvec3 words;", 2, "u32"), ("uvec4 words;", 3, "u32"),
    ("uint words;", 2, "u32"), ("uvec2 words;", 2, "f64"),
    ("ivec2 words;", 2, "u32"),
    ("vec2 words;", 2, "u32"), ("uvec2 words[2];", 4, "u32"),
    ("uvec2 words[1][1];", 2, "u32"),
])
def test_unsigned_vector_does_not_relax_record_shape_or_type(core, bake, declaration, count, kind):
    with pytest.raises(ValueError, match="words"):
        _record_block(core, bake, declaration, count, kind=kind)


def test_bool_vector_lowering_uses_the_actual_unsigned_reflected_contract(core, bake, tmp_path):
    pack = bake("#version 440\nlayout(std140, binding = 2) uniform Probe { bvec2 words; };\n"
                "layout(location = 0) out vec4 fragColor;\nvoid main() { fragColor = vec4(float(words.x)); }\n",
                "bool_vector.frag")
    member = _reflection(pack, tmp_path / "bool_vector.qsb")["uniformBlocks"][0]["members"][0]
    assert member["type"] == "uvec2" and not member.get("arrayDims")
    values = [0x80000000, 0xFFFFFFFF]
    data, row = _record_block(core, bake, "bvec2 words;", 2, values=values)
    assert struct.unpack_from("<2I", data, row[2]) == tuple(values)


@pytest.mark.parametrize("declaration,bound", [("int words;", 2147483647), ("float words;", 16777216)])
def test_scalar_unsigned_range_rule_is_still_required(core, bake, declaration, bound):
    with pytest.raises(ValueError, match="range rule"):
        _record_block(core, bake, declaration, 1, values=[1])
    with pytest.raises(ValueError, match="range rule"):
        _record_block(core, bake, declaration, 1, checks=(("words", "at_most", bound + 1),), values=[1])
    data, member = _record_block(core, bake, declaration, 1,
                                 checks=(("words", "at_most", bound),), values=[bound])
    assert struct.unpack_from("<i" if declaration.startswith("int") else "<f", data, member[2])[0] == bound


@pytest.mark.parametrize("bad", [[-1, 1, 2, 3], [1, 2, 3, 4294967296], [1, 2, 3], [1, 2, 3, 4, 5]])
def test_unsigned_vector_settings_keep_range_and_size_rejection(core, bake, bad):
    pack = bake("#version 440\nlayout(std140, binding = 2) uniform Probe { uvec4 words; };\n"
                "layout(location = 0) out vec4 fragColor;\nvoid main() { fragColor = vec4(words); }\n",
                "settings_vector.frag")
    with pytest.raises(ValueError, match="words"):
        core.program_block_pack(pack, "Probe", {"words": bad})


def _uniform_source(stage, kind, count, *, storage=False):
    declaration = ("layout(std430, binding = 3) readonly buffer Inputs" if storage else
                   "layout(std140, binding = 2) uniform Probe") + f" {{ {kind} values[{count}]; }};\n"
    component = ".x" if "vec" in kind else ""
    read = f"vec4(float(values[0]{component}) + float(values[{count - 1}]{component}))"
    if stage == "comp":
        return ("#version 440\nlayout(local_size_x = 1) in;\n" + declaration +
                "layout(std430, binding = 6) writeonly buffer Sink { vec4 result; };\n"
                "void main() { result = " + read + "; }\n")
    return _source(stage, "conventions", present=False).replace("#version 440\n", "#version 440\n" + declaration).replace(
        "vec4(0.0)", read)


def _admit_uniform(core, bake, owner, kind, count, *, storage=False):
    import mesh_buffers as mb
    from rendering.native.mode import (ComputeBinding, ComputePass, ModePass, ModeStream, PassGeometry,
                                       StorageBuffer, program_json, schema_table_entry)

    suffix = {"fullscreen": "frag", "vertex": "vert", "fragment": "frag", "compute": "comp"}[owner]
    pack = bake(_uniform_source(suffix, kind, count, storage=storage), f"uniform_{owner}.{suffix}")
    vertex = bake(_source("vert", "conventions", present=False), "control.vert")
    fragment = bake(_source("frag", "conventions", present=False), "control.frag")
    buffers, streams = (), ()
    geometry = PassGeometry(vertex, vertices="count", instances=1)
    fields, record = (("count", "u32", 1),), {"count": 3}
    if storage:
        fields += (("payload", "f32", 8), ("used", "u32", 1))
        record.update(payload=struct.pack("<8I", *range(8)), used=8)
        streams = (ModeStream("payload", "payload", used="used"),)
        geometry = PassGeometry(pack, vertices="count", instances=1, storage=(("Inputs", "payload"),))
        passes = (ModePass("probe", fragment, "replace", geometry=geometry),)
    elif owner in ("vertex", "fragment"):
        passes = (ModePass("probe", fragment if owner == "vertex" else pack, "replace",
                           geometry=PassGeometry(pack if owner == "vertex" else vertex,
                                                 vertices="count", instances=1)),)
    else:
        probe = ModePass("probe", pack, "replace")
        if owner == "compute":
            buffers = (StorageBuffer("sink", 16),)
            probe = ComputePass("probe", pack, groups=(1, 1, 1),
                                bindings=(ComputeBinding("Sink", "sink", "buffer", "write"),))
        passes = (probe, ModePass("control", fragment, "replace", geometry=geometry))
    declared, packs = program_json(passes, streams=streams, buffers=buffers)
    checks = (("used", "at_most", 8),) if storage else ()
    schema = mb.schema("unsigned_uniform", fields, checks, code=250)
    components = int(kind[-1]) if "vec" in kind else 1
    values = [1] * (count * components)
    settings = {} if storage else {"values": values}
    return core.module.mode_blocks(json.dumps(schema_table_entry(schema)), declared, packs, json.dumps(settings),
                                   schema.encode(record), None, (64, 64))


@pytest.mark.parametrize("kind", ["uint", "uvec2", "uvec3", "uvec4", "bool", "bvec2", "bvec3", "bvec4"])
@pytest.mark.parametrize("count", [1, 2], ids=["one_element_supported", "multiple_elements_refused"])
def test_unsigned_and_bool_uniform_arrays_are_portably_admitted_only_at_length_one(core, bake, tmp_path, kind, count):
    pack = bake(_uniform_source("frag", kind, count), "reflection.frag")
    member = _reflection(pack, tmp_path / "reflection.qsb")["uniformBlocks"][0]["members"][0]
    # SPIR-V uniform storage lowers GLSL bool/bvecN to uint/uvecN; admission follows the actual reflected type.
    reflected_kind = "uint" if kind == "bool" else "u" + kind[1:] if kind.startswith("bvec") else kind
    assert member["type"] == reflected_kind and member["arrayDims"] == [count]
    if count == 1:
        _admit_uniform(core, bake, "fullscreen", kind, count)
    else:
        with pytest.raises(ValueError, match=r"probe.*Probe.*values.*unsigned/bool.*array"):
            _admit_uniform(core, bake, "fullscreen", kind, count)
    # Generic CPU reflection/packing is not a portable rendering admission owner.
    data, facts = core.program_block_pack(pack, "Probe", {"values": [1] * (count * (int(kind[-1]) if "vec" in kind else 1))})
    row = facts["layout"]["members"][0]
    assert not facts["unfilled"] and row[3] == count
    assert struct.unpack_from("<I", data, row[2])[0] == 1
    if count > 1:
        assert struct.unpack_from("<I", data, row[2] + row[4])[0] == 1


@pytest.mark.parametrize("owner", ["vertex", "fragment", "compute"])
@pytest.mark.parametrize("kind", ["uint", "bvec4"])
@pytest.mark.parametrize("count", [1, 2])
def test_all_shader_owners_enforce_the_same_uniform_array_contract(core, bake, owner, kind, count):
    if count == 1:
        _admit_uniform(core, bake, owner, kind, count)
    else:
        with pytest.raises(ValueError, match=r"probe.*Probe.*values.*unsigned/bool.*array"):
            _admit_uniform(core, bake, owner, kind, count)


@pytest.mark.parametrize("kind", ["uint", "uvec4", "bool", "bvec4"])
def test_unsigned_and_bool_storage_arrays_remain_admitted(core, bake, kind):
    _admit_uniform(core, bake, "vertex", kind, 2, storage=True)


@pytest.mark.parametrize("kind", ["int", "ivec4", "float", "vec4"])
def test_other_uniform_array_types_remain_admitted(core, bake, kind):
    _admit_uniform(core, bake, "fullscreen", kind, 2)


@pytest.mark.parametrize("shape", ["member_array", "struct_array"])
def test_nested_uniform_admission_distinguishes_leaf_arrays_from_enclosing_struct_arrays(core, bake, shape):
    from rendering.native.mode import ModePass

    field = "uint word[2];" if shape == "member_array" else "uint word;"
    member = "Nested nested;" if shape == "member_array" else "Nested nested[2];"
    read = "nested.word[1]" if shape == "member_array" else "nested[1].word"
    pack = bake("#version 440\nstruct Nested { " + field + " };\n"
                "layout(std140, binding = 2) uniform Probe { " + member + " };\n"
                "layout(location = 0) out vec4 fragColor;\nvoid main() { fragColor = vec4(float(" + read + ")); }\n",
                "nested_array.frag")
    passes = (ModePass("probe", pack, "replace"),)
    if shape == "member_array":
        with pytest.raises(ValueError, match=r"probe.*Probe.*nested.word.*unsigned/bool.*array"):
            core.mode_program_layout(passes)
    else:
        # Admission only: generic CPU block packing does not gain struct support. Qt expands the enclosing
        # struct array into individually named scalar leaves, so this is not the unsigned-array upload bug.
        facts = core.mode_program_layout(passes)
        assert facts["passes"][0]["block"]["name"] == "Probe"
