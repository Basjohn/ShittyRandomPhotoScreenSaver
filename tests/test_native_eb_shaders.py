"""N5.6: Extruded Bubble's native packs are the Python renderer's texts, each program's members named for it
(``rendering/native/extruded_bubble_shaders.py``, ``tools/eb_native_shaders.py``).

Each check has its control: the Python text as it is (shared member names, unlocated varyings) fails it.
"""
from __future__ import annotations

import re

import pytest


def _defines(text: str) -> dict[str, str]:
    return dict(re.findall(r"^#define (\w+) (\w+)$", text, re.M))


def test_every_program_names_each_block_member_for_itself_and_keeps_the_core_members():
    from rendering.native.extruded_bubble_shaders import PROGRAMS, block_members, member_name, shader_files
    from rendering.native.mode import MODE_CORE_MEMBERS

    files = shader_files()
    owners: dict[str, str] = {}
    for program in PROGRAMS:
        for stage in ("vert", "frag"):
            renamed = {k: v for k, v in _defines(files[f"eb_{program}.{stage}"]).items() if k in block_members(program)}
            expected = {m: member_name(program, m) for m in block_members(program) if m not in MODE_CORE_MEMBERS}
            assert renamed == expected
        for member in block_members(program):
            name = member_name(program, member)
            if member in MODE_CORE_MEMBERS:
                assert name == member
            else:
                assert owners.setdefault(name, program) == program     # no other program fills this name
    # Control: without the prefixes two programs would share a name the core fills from one source.
    assert member_name("shells", "uTime") != member_name("near", "uTime")
    from rendering.gl_programs.extruded_bubble_program import BUBBLE_FRAGMENT
    assert not set(_defines(BUBBLE_FRAGMENT)) & set(block_members("shells"))


def test_the_texts_are_the_python_texts_apart_from_the_names_and_the_core_variants():
    from rendering.gl_programs import extruded_bubble_program as p
    from rendering.native.extruded_bubble_shaders import shader_files, sorted_text

    files = shader_files()
    body = files["eb_backdrop.frag"].split("\n", 1)[1]
    body = re.sub(r"\} blk_\w+;", "};", body)
    body = "\n".join(line for line in body.splitlines()
                     if not line.startswith(("#define u", "// Extruded Bubble")) and " blk_" not in line)
    assert body.strip() == p.BACKDROP_FRAGMENT.split("\n", 1)[1].strip()
    assert "SceneColour" in files["eb_shells_sorted.frag"] and "SceneAccum" not in files["eb_shells_sorted.frag"]
    assert "layout(location=1) out vec4 Emission;" in files["eb_shells_sorted.frag"]
    # The probe's proxies keep their emission as a plain variable (one cube attachment).
    assert "out vec4 Emission" not in files["eb_proxies.frag"] and "out vec4 Emission" in files["eb_specks.frag"]
    with pytest.raises(ValueError):
        sorted_text(p.PARTICLE_FRAGMENT)      # control: an opaque fragment has no order-independent outputs


def test_every_varying_is_located_and_paired_by_name():
    from rendering.gl_programs import extruded_bubble_program as p
    from rendering.native.extruded_bubble_shaders import PROGRAMS, shader_files

    unlocated = re.compile(r"^(?:flat\s+)?(?:in|out)\s+\w+\s+\w+", re.M)
    files = shader_files()
    for program in PROGRAMS:
        vertex, fragment = files[f"eb_{program}.vert"], files[f"eb_{program}.frag"]
        assert not unlocated.search(vertex) and not unlocated.search(fragment), program
        outs = dict((n, l) for l, n in re.findall(r"location=(\d+)\)\s*(?:flat\s+)?out\s+\w+\s+(\w+)", vertex))
        ins = dict((n, l) for l, n in re.findall(r"location=(\d+)\)\s*(?:flat\s+)?in\s+\w+\s+(\w+)", fragment))
        assert all(outs[name] == location for name, location in ins.items()), program
    # Controls: an unlocated declaration is found, and a fragment input its vertex stage never writes is refused.
    from rendering.native.extruded_bubble_shaders import _located

    assert unlocated.search("#version 460 core\nin vec2 vNdc;\n")
    with pytest.raises(ValueError):
        _located(p.FULL_VERTEX, "#version 460 core\nin vec2 vMissing;\n")


_GL_UNIFORM = re.compile(r"^uniform\s+(\w+)\s+(\w+)\s*;", re.M)
_GL_BUFFER = re.compile(r"\bbuffer\s+(\w+)\s*\{[^{}]*\}\s*(\w+)\s*;")


def _gl_globals(pack: bytes) -> dict[str, str]:
    """Each OpenGL translation's global uniform and storage instance names and their types (every GLSL version)."""
    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QShader

    shader = QShader.fromSerialized(QByteArray(pack))
    names: dict[str, str] = {}
    for key in shader.availableShaders():
        if key.source() == QShader.Source.GlslShader:
            text = bytes(shader.shader(key).shader()).decode()
            for kind, name in (*_GL_UNIFORM.findall(text), *_GL_BUFFER.findall(text)):
                names[f"{key.sourceVersion().version()}:{name}"] = kind
    return names


def _clashes(vertex: bytes, fragment: bytes) -> list[str]:
    """The names both stages' OpenGL texts declare with different types (OpenGL refuses to link them)."""
    a, b = _gl_globals(vertex), _gl_globals(fragment)
    return sorted(f"{name}: {a[name]} / {b[name]}" for name in set(a) & set(b) if a[name] != b[name])


def test_no_program_declares_one_opengl_uniform_name_with_two_types():
    # OpenGL links the stages' uniforms by name: the trails program's vertex EbTrails and its fragment's
    # SrpssConventions were both ``_449`` (28 Nov), so its pipeline could not be created.
    pytest.importorskip("PySide6")
    from rendering.native.extruded_bubble_shaders import PROGRAMS, TRANSPARENT, pack

    found = {}
    for program in PROGRAMS:
        fragments = [f"eb_{program}.frag"] + ([f"eb_{program}_sorted.frag"] if program in TRANSPARENT else [])
        for fragment in fragments:
            clashes = _clashes(pack(f"eb_{program}.vert"), pack(fragment))
            if clashes:
                found[fragment] = clashes
    assert not found
    # Control: a vertex block and a fragment block of different types under one name is a clash.
    assert _GL_UNIFORM.findall("uniform EbTrails _449;\n") == [("EbTrails", "_449")]


def test_every_anonymous_block_is_named_alike_in_every_stage():
    from rendering.native.extruded_bubble_shaders import PROGRAMS, _instanced, instance_name, shader_files

    anonymous = re.compile(r"(?:uniform|buffer)\s+\w+\s*\{[^{}]*\}\s*;")
    files = shader_files()
    for program in PROGRAMS:
        for name in (f"eb_{program}.vert", f"eb_{program}.frag"):
            assert not anonymous.search(files[name]), name
        block = f"uniform {'EbTrails'} {{"
        if program == "trails":
            for name in ("eb_trails.vert", "eb_trails.frag"):
                assert f"}} {instance_name('EbTrails')};" in files[name] and block in files[name]
    # Control: the composer's step is what names them (a block left as written stays anonymous).
    text = "layout(std140, binding = 1) uniform EbTrails {\n    float uTime;\n};\nvoid main() { uTime; }\n"
    assert anonymous.search(text) and not anonymous.search(_instanced(text, "trails"))
    assert "#define trails_u_time blk_EbTrails.trails_u_time" in _instanced(text, "trails")


def test_the_committed_packs_are_what_the_texts_bake_to():
    pytest.importorskip("PySide6")
    from tools.eb_native_shaders import statuses

    found = statuses(bake=False)
    assert found and all(current for _name, current, _reason in found), [f for f in found if not f[1]]


def test_the_drift_entries_run_the_python_solver_texts_unchanged_under_a_cursor():
    from rendering.native.extruded_bubble_drift import _globals, compute_texts
    from rendering.quick.visualizer.implementations.extruded_bubble_drift_solver import (
        CHAIN_COMPUTE, CLOUD_COMPUTE, PAIR_CHECK_COMPUTE)
    from widgets.spotify_visualizer.extruded_bubble_drift_log import FAMILIES

    files = compute_texts()
    assert files["eb_drift_pair_check.comp"] == PAIR_CHECK_COMPUTE
    for family in FAMILIES:
        python = CHAIN_COMPUTE if family == "chains" else CLOUD_COMPUTE
        body = python.split("void main() {", 1)[1]
        for entry in ("_before", ""):
            text = files[f"eb_drift_{family}{entry}.comp"]
            assert "uniform DriftDispatch" not in text and text.count("void main() {") == 1
            assert "void driftRun() {" + body.split("\n}\n", 1)[0] in text      # the arithmetic as it is
            assert f"uniform EbDrift_{family}" in text and "driftRun();" in text
        mark = files[f"eb_drift_{family}_mark.comp"]
        assert "driftRun" not in mark and "header[0] = uvec4(" in mark
    # Control: a text without its DriftDispatch block (or with two mains) is refused, not silently left as it is.
    with pytest.raises(ValueError):
        _globals(PAIR_CHECK_COMPUTE)
